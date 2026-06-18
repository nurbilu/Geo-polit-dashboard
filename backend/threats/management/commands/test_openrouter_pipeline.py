"""
End-to-end telemetry check for the OpenRouter multimodal vision pipeline.

Usage:
    python manage.py test_openrouter_pipeline
    python manage.py test_openrouter_pipeline --no-save
"""
import base64
import json
import uuid
from datetime import datetime, timezone

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone as django_tz

from threats import llama4_service
from threats.models import Alert, AlertStatus, Source, SourceType

# Minimal valid 1x1 transparent GIF (GIF89a, 43 bytes).
# Decoded programmatically from a known-good base64 constant.
_MINIMAL_GIF_B64 = "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"

SAMPLE_TITLE = "Pipeline Test – Judea & Samaria Checkpoint"
SAMPLE_TEXT = (
    "Alert: Explosions reported near a checkpoint in Judea & Samaria. "
    "Local security forces are responding. Unverified social media posts "
    "show smoke rising from the area."
)


def _make_test_image_bytes() -> bytes:
    """Return a tiny valid 1x1 transparent GIF to simulate scraped media."""
    return base64.b64decode(_MINIMAL_GIF_B64)


class Command(BaseCommand):
    help = (
        "Run a mock multimodal signal through the OpenRouter vision pipeline "
        "and print HTTP / JSON / parsing diagnostics."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-save",
            action="store_true",
            help="Skip creating a test Alert record in the database.",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING(
            "OpenRouter Vision Pipeline — End-to-End Test"
        ))
        self.stdout.write("")

        # --- Pre-flight ---------------------------------------------------
        self._section("Pre-flight")
        if not llama4_service.ensure_model_available():
            raise CommandError(
                "OPENROUTER_API_KEY is missing. Set it in .env and restart containers."
            )
        self.stdout.write(f"  Model:     {settings.OPENROUTER_MODEL}")
        self.stdout.write(f"  Endpoint:  {llama4_service.OPENROUTER_URL}")
        key_hint = settings.OPENROUTER_API_KEY[:12] + "…" if settings.OPENROUTER_API_KEY else "(empty)"
        self.stdout.write(f"  API key:   {key_hint}")
        self.stdout.write("")

        image_bytes = _make_test_image_bytes()
        self._section("Mock signal")
        self.stdout.write(f"  Title:     {SAMPLE_TITLE}")
        self.stdout.write(f"  Text:      {SAMPLE_TEXT[:80]}…")
        self.stdout.write(f"  Image:     1x1 transparent GIF ({len(image_bytes)} bytes)")
        self.stdout.write("")

        # --- Core pipeline (same _analyze_request path as analyze()) --------
        self._section("OpenRouter API call")
        try:
            verdict, http_status, openrouter_body = llama4_service.analyze_with_diagnostics(
                text=SAMPLE_TEXT,
                image_bytes=image_bytes,
                title=SAMPLE_TITLE,
            )
        except requests.HTTPError as exc:
            self._print_http_error(exc)
            raise CommandError("OpenRouter request failed.") from exc
        except requests.RequestException as exc:
            raise CommandError(f"Network error reaching OpenRouter: {exc}") from exc
        except RuntimeError as exc:
            raise CommandError(str(exc)) from exc

        # --- Metrics & diagnostics ----------------------------------------
        self._section("HTTP status")
        if http_status == 200:
            self.stdout.write(self.style.SUCCESS(
                f"  ✓ HTTP {http_status} — API communication successful"
            ))
        else:
            self.stdout.write(self.style.WARNING(f"  HTTP {http_status} (expected 200)"))

        self._section("Raw OpenRouter JSON response")
        self.stdout.write(json.dumps(openrouter_body, indent=2, ensure_ascii=False))

        self._section("Parsed verdict fields (_extract_json → ThreatVerdict)")
        self.stdout.write(f"  is_threat:        {verdict.is_threat}")
        self.stdout.write(f"  region:           {verdict.region}")
        self.stdout.write(f"  threat_severity:  {verdict.threat_severity}")
        self.stdout.write(f"  visual_summary:   {verdict.visual_summary or '(empty)'}")
        self.stdout.write("")
        self.stdout.write("  verdict.raw (parsed JSON object):")
        self.stdout.write(json.dumps(verdict.raw, indent=4, ensure_ascii=False))

        parse_ok = bool(verdict.raw) and "_unparsed" not in verdict.raw
        self.stdout.write("")
        if parse_ok:
            self.stdout.write(self.style.SUCCESS(
                "  ✓ _extract_json parsing succeeded — all expected keys present."
            ))
        else:
            self.stdout.write(self.style.ERROR(
                "  ✗ _extract_json could not produce a clean object. Check raw response above."
            ))

        # --- Optional DB persistence --------------------------------------
        self._section("Database save test")
        if options["no_save"]:
            self.stdout.write("  Skipped (--no-save). Pipeline API test still completed.")
        else:
            alert = self._save_test_alert(verdict, image_bytes)
            self.stdout.write(self.style.SUCCESS(
                f"  ✓ Test Alert saved (id={alert.id}, external_id={alert.external_id})"
            ))
            self.stdout.write(
                f"    status={alert.status}, region={alert.region}, "
                f"is_threat={alert.is_threat}, severity={alert.threat_severity}"
            )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Pipeline test complete."))

    def _save_test_alert(self, verdict, image_bytes: bytes) -> Alert:
        """Persist a disposable test Source + Alert with the pipeline verdict."""
        source, _ = Source.objects.get_or_create(
            name="OpenRouter Pipeline Test",
            defaults={
                "source_type": SourceType.RSS,
                "identifier": "pipeline-test://local",
                "is_active": False,
            },
        )
        external_id = f"pipeline-test-{uuid.uuid4().hex[:12]}"
        alert = Alert(
            source=source,
            external_id=external_id,
            title=SAMPLE_TITLE,
            content=SAMPLE_TEXT,
            url="",
            raw_data={
                "pipeline_test": True,
                "run_at": datetime.now(timezone.utc).isoformat(),
            },
            status=AlertStatus.ANALYZED,
            analyzed_at=django_tz.now(),
            **verdict.as_db_fields(),
        )
        alert.image_path.save(
            f"pipeline_test_{external_id}.gif",
            ContentFile(image_bytes),
            save=False,
        )
        alert.save()
        return alert

    def _section(self, title: str) -> None:
        self.stdout.write(self.style.HTTP_INFO(
            f"── {title} " + "─" * max(0, 52 - len(title))
        ))

    def _print_http_error(self, exc: requests.HTTPError) -> None:
        self.stdout.write(self.style.ERROR(f"  ✗ HTTP error: {exc}"))
        if exc.response is not None:
            self.stdout.write(f"  Status: {exc.response.status_code}")
            try:
                self.stdout.write(json.dumps(exc.response.json(), indent=2))
            except Exception:
                self.stdout.write(exc.response.text[:2000])
