"""
Celery tasks:
  - startup_catchup: fires once on worker boot to backfill the downtime window.
  - poll_all_sources / poll_source: incremental ingestion from each source.
  - download_media: fetch + persist scraped images locally.
  - analyze_alert: multimodal OpenRouter Vision pipeline (text + image -> JSON verdict).
  - rebuild_metrics: roll up dashboard counters.

Source connectors (Telegram/X/RSS/Gov) are intentionally pluggable. RSS is wired
with `feedparser`; the others expose clearly marked stubs to fill with real
credentials/clients without touching the orchestration logic.
"""
import logging
import mimetypes
import re
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone

import requests
from celery import shared_task
from django.conf import settings
from django.core.files.base import ContentFile
from django.db.models import Avg, Count, F, Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from . import llama4_service, notification_service
from .models import Alert, AlertStatus, Metric, Region, Source, SourceType

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 30
MAX_IMAGE_BYTES = 12 * 1024 * 1024  # 12 MB safety cap.

# Primary alerts at/above this severity trigger an instant Telegram notification.
CRITICAL_SEVERITY_THRESHOLD = 8

# --- Deduplication / clustering tuning ---
DEDUP_WINDOW_MINUTES = 15      # only cluster with events seen this recently
DEDUP_CANDIDATE_LIMIT = 50     # cap candidates scanned per analysis (low overhead)
DEDUP_JACCARD_THRESHOLD = 0.35  # keyword-set similarity to treat as the same event
DEDUP_MIN_SHARED_KEYWORDS = 4  # or this many shared keywords (helps long texts)

# Latin (>=3 chars) and Hebrew word tokens; digits/punctuation ignored.
_KEYWORD_RE = re.compile(r"[a-zA-Z\u0590-\u05FF]{3,}")
_STOPWORDS = {
    "the", "and", "for", "are", "was", "were", "with", "that", "this", "from",
    "have", "has", "had", "not", "but", "you", "your", "our", "who", "will",
    "near", "into", "onto", "over", "under", "reported", "reports", "report",
    "alert", "update", "breaking", "local", "area", "areas", "said", "says",
}


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


TELEGRAM_PREVIEW_BASE = "https://t.me/s/"
_TG_BG_RE = re.compile(r"background-image:\s*url\(['\"]?(.*?)['\"]?\)")


def _telegram_channel_name(identifier: str) -> str:
    """
    Normalize a Source.identifier into a bare public channel name.

    Accepts: '@channel', 'channel', 't.me/channel', 'https://t.me/s/channel', etc.
    """
    s = (identifier or "").strip()
    for prefix in (
        "https://t.me/s/", "http://t.me/s/", "https://t.me/", "http://t.me/",
        "t.me/s/", "t.me/",
    ):
        if s.startswith(prefix):
            s = s[len(prefix):]
            break
    s = s.lstrip("@").strip("/")
    if s.startswith("s/"):
        s = s[2:]
    # Keep only the first path segment, drop query string.
    return s.split("/")[0].split("?")[0].strip()


def _fetch_telegram(source, since=None):
    """
    Anonymous OSINT connector for public Telegram channels.

    Scrapes the public web preview at ``https://t.me/s/<channel>`` (no API keys,
    no login) and extracts the latest text posts (and any attached photo URL).
    De-duplication is handled upstream via the (source, external_id) constraint,
    where ``external_id`` is the Telegram ``data-post`` value (e.g. "channel/123").
    """
    import httpx
    from bs4 import BeautifulSoup

    channel = _telegram_channel_name(source.identifier)
    if not channel:
        logger.warning("Telegram source %s has no parseable channel name.", source.id)
        return []

    url = f"{TELEGRAM_PREVIEW_BASE}{channel}"
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; ThreatDashboard/1.0; +osint)",
        "Accept-Language": "en,he;q=0.9",
    }
    resp = httpx.get(
        url, headers=headers, timeout=REQUEST_TIMEOUT, follow_redirects=True
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    items = []
    for bubble in soup.select("div.tgme_widget_message"):
        data_post = bubble.get("data-post")  # e.g. "channelname/1234"
        if not data_post:
            continue

        text_el = bubble.select_one(".tgme_widget_message_text")
        content = text_el.get_text("\n", strip=True) if text_el else ""

        published = None
        time_el = bubble.select_one("time[datetime]")
        if time_el and time_el.get("datetime"):
            published = parse_datetime(time_el["datetime"])
        if since and published and published <= since:
            continue

        image_url = None
        photo = bubble.select_one(".tgme_widget_message_photo_wrap")
        if photo and photo.get("style"):
            match = _TG_BG_RE.search(photo["style"])
            if match:
                image_url = match.group(1)

        # Skip empty bubbles (e.g. service messages with neither text nor photo).
        if not content and not image_url:
            continue

        title = (content.split("\n", 1)[0][:200] if content
                 else f"Telegram post {data_post}")
        items.append(
            {
                "external_id": data_post,
                "title": title,
                "content": content,
                "url": f"https://t.me/{data_post}",
                "image_url": image_url,
                "published_at": published,
                "raw": {
                    "channel": channel,
                    "data_post": data_post,
                    "scraped_from": url,
                },
            }
        )

    logger.info("Telegram scrape %s: %s message(s).", channel, len(items))
    return items


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
    """Run the configured AI provider (Llama 4 Scout via Groq by default) over
    the alert's text (and image, if any) and store the structured verdict."""
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

    now = timezone.now()
    fields = verdict.as_db_fields()
    fields["status"] = AlertStatus.ANALYZED
    fields["analyzed_at"] = now

    # --- Deduplication / clustering -------------------------------------
    # Group this item under an existing primary alert for the same event when
    # one was seen very recently in the same region with overlapping keywords.
    parent_id = _cluster_parent_id(alert, verdict, now)
    if parent_id is not None:
        fields["parent_alert_id"] = parent_id
    Alert.objects.filter(id=alert_id).update(**fields)

    if parent_id is not None:
        # Single-row atomic bump: no table lock, safe under active polling.
        Alert.objects.filter(id=parent_id).update(
            cluster_count=F("cluster_count") + 1,
            updated_at=now,
        )
        logger.info("Alert %s clustered under primary %s.", alert_id, parent_id)

    # --- Critical-threat alerting ---------------------------------------
    # Only fire for primary (non-duplicate) alerts at/above the threshold. The
    # dispatch is queued as its own task so a slow Telegram response can never
    # delay this analysis loop.
    notified = False
    if (
        parent_id is None
        and (verdict.threat_severity or 0) >= CRITICAL_SEVERITY_THRESHOLD
    ):
        dispatch_critical_notification.delay(alert_id)
        notified = True

    # Update rollups for the affected day/region.
    rebuild_metrics.delay(
        region=verdict.region, day=alert.published_at.date().isoformat()
    )
    return {
        "alert": alert_id,
        "status": "analyzed",
        "is_threat": verdict.is_threat,
        "clustered_under": parent_id,
        "critical_notified": notified,
    }


# ---------------------------------------------------------------------------
# Critical-threat notification dispatch
# ---------------------------------------------------------------------------
@shared_task(ignore_result=True)
def dispatch_critical_notification(alert_id):
    """
    Send an instant Telegram notification for a critical primary alert.

    Runs in its own Celery task (queued via .delay) so the network round-trip to
    Telegram never blocks the analysis pipeline. Re-validates state defensively.
    """
    try:
        alert = Alert.objects.get(id=alert_id)
    except Alert.DoesNotExist:
        return {"skipped": alert_id}

    if alert.parent_alert_id is not None:
        return {"alert": alert_id, "sent": False, "reason": "not_primary"}
    if (alert.threat_severity or 0) < CRITICAL_SEVERITY_THRESHOLD:
        return {"alert": alert_id, "sent": False, "reason": "below_threshold"}

    sent = notification_service.notify_critical_alert(alert)
    return {"alert": alert_id, "sent": sent}


# ---------------------------------------------------------------------------
# Deduplication / event clustering helpers
# ---------------------------------------------------------------------------
def _keywords(*texts) -> set:
    """Extract a normalized keyword set (latin + hebrew words, no stopwords)."""
    tokens = set()
    for text in texts:
        for match in _KEYWORD_RE.findall((text or "").lower()):
            if match not in _STOPWORDS:
                tokens.add(match)
    return tokens


def _is_similar(a: set, b: set) -> bool:
    """Cheap set-based similarity: Jaccard threshold OR strong shared-keyword count."""
    if not a or not b:
        return False
    shared = len(a & b)
    if shared == 0:
        return False
    if shared >= DEDUP_MIN_SHARED_KEYWORDS:
        return True
    union = len(a | b)
    return (shared / union) >= DEDUP_JACCARD_THRESHOLD


def _cluster_parent_id(alert, verdict, now):
    """
    Find a recent primary alert in the same region describing the same event.

    Returns the primary alert id to attach to, or None to keep this as a new
    primary. Kept intentionally lightweight: bounded candidate scan, no locks.
    """
    region = verdict.region
    # An unknown region carries no clustering signal; skip to avoid over-merging.
    if region == Region.UNKNOWN:
        return None

    window_start = now - timedelta(minutes=DEDUP_WINDOW_MINUTES)
    new_keywords = _keywords(alert.title, alert.content, verdict.visual_summary)
    if not new_keywords:
        return None

    candidates = (
        Alert.objects.filter(
            region=region,
            parent_alert__isnull=True,          # only cluster under primaries
            status=AlertStatus.ANALYZED,
            analyzed_at__gte=window_start,
        )
        .exclude(id=alert.id)
        .order_by("-analyzed_at")
        .values("id", "title", "content", "visual_summary")[:DEDUP_CANDIDATE_LIMIT]
    )

    for cand in candidates:
        cand_keywords = _keywords(
            cand["title"], cand["content"], cand["visual_summary"]
        )
        if _is_similar(new_keywords, cand_keywords):
            return cand["id"]
    return None


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
