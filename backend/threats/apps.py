import logging
import os

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class ThreatsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "threats"

    def ready(self):
        """
        Fire an immediate "catch-up" sync when the worker boots so we backfill
        whatever was missed while the stack was shut down.

        Only the Celery worker process should trigger this (guarded by an env
        flag set in entrypoint.sh) to avoid the web/beat processes double-firing.
        """
        if os.environ.get("RUN_STARTUP_CATCHUP") != "1":
            return
        try:
            from .tasks import startup_catchup

            startup_catchup.apply_async(countdown=5)
            logger.info("Queued startup catch-up sync task.")
        except Exception:  # pragma: no cover - never block boot on this
            logger.exception("Failed to queue startup catch-up task.")
