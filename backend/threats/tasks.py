"""
Celery tasks:
  - startup_catchup: fires once on worker boot to backfill the downtime window.
  - poll_all_sources / poll_source: incremental ingestion from each source.
  - download_media: fetch + persist scraped images locally.
  - analyze_alert: multimodal Llama 4 Scout pipeline (text + image -> JSON verdict).
  - rebuild_metrics: roll up dashboard counters.

Source connectors (Telegram/X/RSS/Gov) are intentionally pluggable. RSS is wired
with `feedparser`; the others expose clearly marked stubs to fill with real
credentials/clients without touching the orchestration logic.
"""
import logging
import mimetypes
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone

import requests
from celery import shared_task
from django.conf import settings
from django.core.files.base import ContentFile
from django.db.models import Avg, Count, Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from . import llama4_service
from .models import Alert, AlertStatus, Metric, Region, Source, SourceType

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 30
MAX_IMAGE_BYTES = 12 * 1024 * 1024  # 12 MB safety cap.


# ---------------------------------------------------------------------------
# Startup catch-up
# ---------------------------------------------------------------------------
@shared_task(ignore_result=True)
def startup_catchup():
    """
    Backfill data missed while the stack was offline. Runs once shortly after
    the worker boots (queued from threats.apps.ThreatsConfig.ready).
    """
    window = timezone.now() - timedelta(hours=settings.CATCHUP_WINDOW_HOURS)
    logger.info("Startup catch-up: backfilling since %s", window.isoformat())

    active = Source.objects.filter(is_active=True)
    queued = 0
    for source in active:
        # Sources never synced, or stale beyond the window, get a catch-up pull.
        if source.last_synced_at is None or source.last_synced_at < timezone.now():
            poll_source.delay(source.id, catchup_since=window.isoformat())
            queued += 1

    # Re-queue any alerts that were left mid-flight when we shut down.
    stuck = Alert.objects.filter(
        status__in=[AlertStatus.PENDING, AlertStatus.PROCESSING]
    ).values_list("id", flat=True)
    for alert_id in stuck:
        analyze_alert.delay(alert_id)

    logger.info(
        "Startup catch-up queued %s source pulls and %s pending analyses.",
        queued, len(stuck),
    )
    return {"sources": queued, "pending_alerts": len(stuck)}


# ---------------------------------------------------------------------------
# Source polling
# ---------------------------------------------------------------------------
@shared_task(ignore_result=True)
def poll_all_sources():
    """Periodic fan-out: queue an incremental poll for every active source."""
    ids = Source.objects.filter(is_active=True).values_list("id", flat=True)
    for source_id in ids:
        poll_source.delay(source_id)
    return {"queued": len(ids)}


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def poll_source(self, source_id, catchup_since=None):
    """
    Pull new items for a single source and persist them as PENDING alerts.

    Dispatches to a per-type connector. Each connector returns a list of dicts:
        {external_id, title, content, url, image_url, published_at, raw}
    """
    try:
        source = Source.objects.get(id=source_id, is_active=True)
    except Source.DoesNotExist:
        return {"skipped": source_id}

    since = parse_datetime(catchup_since) if catchup_since else source.last_synced_at

    connectors = {
        SourceType.RSS: _fetch_rss,
        SourceType.TELEGRAM: _fetch_telegram,
        SourceType.X: _fetch_x,
        SourceType.GOV: _fetch_gov,
    }
    fetch = connectors.get(source.source_type)
    if fetch is None:
        logger.warning("No connector for source type %s", source.source_type)
        return {"source": source_id, "created": 0}

    try:
        items = fetch(source, since=since)
    except Exception as exc:  # transient network/source errors -> retry
        logger.exception("Fetch failed for source %s", source_id)
        raise self.retry(exc=exc)

    created = 0
    newest_external_id = source.last_external_id
    for item in items:
        alert, was_created = _persist_item(source, item)
        if was_created:
            created += 1
            newest_external_id = item.get("external_id") or newest_external_id
            # Kick off multimodal analysis (downloads media first if present).
            if alert.image_url:
                download_media.apply_async(
                    args=[alert.id], link=analyze_alert.si(alert.id)
                )
            else:
                analyze_alert.delay(alert.id)

    Source.objects.filter(id=source.id).update(
        last_synced_at=timezone.now(),
        last_external_id=newest_external_id,
    )
    logger.info("Source %s (%s): %s new alert(s).", source.name, source.source_type, created)
    return {"source": source_id, "created": created}


def _persist_item(source, item):
    """Idempotent upsert keyed on (source, external_id)."""
    published = item.get("published_at")
    if isinstance(published, str):
        published = parse_datetime(published) or timezone.now()
    defaults = {
        "title": (item.get("title") or "")[:500],
        "content": item.get("content") or "",
        "url": (item.get("url") or "")[:1000],
        "image_url": item.get("image_url") or None,
        "raw_data": item.get("raw") or {},
        "published_at": published or timezone.now(),
    }
    obj, created = Alert.objects.get_or_create(
        source=source,
        external_id=str(item.get("external_id"))[:255],
        defaults=defaults,
    )
    return obj, created


# ---------------------------------------------------------------------------
# Source connectors
# ---------------------------------------------------------------------------
def _fetch_rss(source, since=None):
    """RSS/Atom feed connector (also works for many Gov news feeds)."""
    import feedparser

    parsed = feedparser.parse(source.identifier)
    items = []
    for entry in parsed.entries:
        published = None
        if getattr(entry, "published_parsed", None):
            published = datetime(*entry.published_parsed[:6], tzinfo=dt_timezone.utc)
        if since and published and published <= since:
            continue

        image_url = None
        if getattr(entry, "media_content", None):
            image_url = entry.media_content[0].get("url")
        elif getattr(entry, "links", None):
            for link in entry.links:
                if link.get("type", "").startswith("image/"):
                    image_url = link.get("href")
                    break

        items.append(
            {
                "external_id": entry.get("id") or entry.get("link"),
                "title": entry.get("title", ""),
                "content": entry.get("summary", ""),
                "url": entry.get("link", ""),
                "image_url": image_url,
                "published_at": published,
                "raw": {k: str(v) for k, v in entry.items()},
            }
        )
    return items


def _fetch_telegram(source, since=None):
    """
    Telegram channel connector.

    Plug in Telethon/Bot API here. Yield dicts with `image_url` set when a
    message carries a photo so the media pipeline can download it. Use
    `source.last_external_id` for de-duplication and `since` for catch-up.
    """
    logger.info("Telegram connector stub for %s (since=%s).", source.identifier, since)
    return []


def _fetch_x(source, since=None):
    """X (Twitter) handle connector. Wire the X API v2 client here."""
    logger.info("X connector stub for %s (since=%s).", source.identifier, since)
    return []


def _fetch_gov(source, since=None):
    """Government site connector. Use requests + parser, or an RSS endpoint."""
    logger.info("Gov connector stub for %s (since=%s).", source.identifier, since)
    return []


# ---------------------------------------------------------------------------
# Media download
# ---------------------------------------------------------------------------
@shared_task(bind=True, max_retries=3, default_retry_delay=20)
def download_media(self, alert_id):
    """Download an alert's remote image into local media storage."""
    try:
        alert = Alert.objects.get(id=alert_id)
    except Alert.DoesNotExist:
        return {"skipped": alert_id}

    if not alert.image_url or alert.image_path:
        return {"alert": alert_id, "downloaded": False}

    try:
        resp = requests.get(
            alert.image_url, timeout=REQUEST_TIMEOUT, stream=True,
            headers={"User-Agent": "ThreatDashboard/1.0"},
        )
        resp.raise_for_status()
        content = resp.content[: MAX_IMAGE_BYTES + 1]
        if len(content) > MAX_IMAGE_BYTES:
            logger.warning("Image too large, skipping local save: %s", alert.image_url)
            return {"alert": alert_id, "downloaded": False}

        ext = mimetypes.guess_extension(
            resp.headers.get("Content-Type", "").split(";")[0]
        ) or ".jpg"
        filename = f"alert_{alert.id}{ext}"
        alert.image_path.save(filename, ContentFile(content), save=True)
        logger.info("Downloaded media for alert %s (%s bytes).", alert_id, len(content))
        return {"alert": alert_id, "downloaded": True}
    except Exception as exc:
        logger.exception("Media download failed for alert %s", alert_id)
        # Don't block analysis on media failures after retries are exhausted.
        if self.request.retries >= self.max_retries:
            return {"alert": alert_id, "downloaded": False, "error": str(exc)}
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Multimodal analysis
# ---------------------------------------------------------------------------
@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def analyze_alert(self, alert_id):
    """Run Llama 4 Scout over the alert's text (+ image) and store the verdict."""
    try:
        alert = Alert.objects.select_related("source").get(id=alert_id)
    except Alert.DoesNotExist:
        return {"skipped": alert_id}

    Alert.objects.filter(id=alert_id).update(status=AlertStatus.PROCESSING)

    image_bytes = _read_image_bytes(alert)

    try:
        verdict = llama4_service.analyze(
            text=alert.content,
            image_bytes=image_bytes,
            title=alert.title,
        )
    except Exception as exc:
        logger.exception("Llama4 analysis failed for alert %s", alert_id)
        if self.request.retries >= self.max_retries:
            Alert.objects.filter(id=alert_id).update(status=AlertStatus.FAILED)
            return {"alert": alert_id, "status": "failed", "error": str(exc)}
        raise self.retry(exc=exc)

    fields = verdict.as_db_fields()
    fields["status"] = AlertStatus.ANALYZED
    fields["analyzed_at"] = timezone.now()
    Alert.objects.filter(id=alert_id).update(**fields)

    # Update rollups for the affected day/region.
    rebuild_metrics.delay(
        region=verdict.region, day=alert.published_at.date().isoformat()
    )
    return {"alert": alert_id, "status": "analyzed", "is_threat": verdict.is_threat}


def _read_image_bytes(alert):
    """Return raw image bytes from the local copy, else fetch the remote URL."""
    if alert.image_path:
        try:
            with alert.image_path.open("rb") as fh:
                return fh.read()
        except Exception:
            logger.exception("Could not read local image for alert %s", alert.id)
    if alert.image_url:
        try:
            resp = requests.get(alert.image_url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp.content
        except Exception:
            logger.exception("Could not fetch remote image for alert %s", alert.id)
    return None


# ---------------------------------------------------------------------------
# Metrics rollup
# ---------------------------------------------------------------------------
@shared_task(ignore_result=True)
def rebuild_metrics(region=None, day=None):
    """Recompute the (region, day) metric tile."""
    target_day = day or timezone.now().date().isoformat()
    qs = Alert.objects.filter(published_at__date=target_day)
    if region:
        qs = qs.filter(region=region)
        regions = [region]
    else:
        regions = list(qs.values_list("region", flat=True).distinct())

    for reg in regions:
        reg_qs = qs.filter(region=reg)
        agg = reg_qs.aggregate(
            total=Count("id"),
            threats=Count("id", filter=Q(is_threat=True)),
            avg_sev=Avg("threat_severity"),
        )
        Metric.objects.update_or_create(
            region=reg,
            day=target_day,
            defaults={
                "total_alerts": agg["total"] or 0,
                "threat_alerts": agg["threats"] or 0,
                "avg_severity": round(agg["avg_sev"] or 0.0, 2),
            },
        )
    return {"day": target_day, "regions": regions}
