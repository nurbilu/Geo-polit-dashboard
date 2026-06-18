"""Relational models for sources, alerts (multimodal), and metrics."""
from django.db import models
from django.utils import timezone


class Region(models.TextChoices):
    JUDEA_SAMARIA = "judea_samaria", "Judea & Samaria"
    GOLAN_HEIGHTS = "golan_heights", "Golan Heights"
    NORTH = "north", "North"
    SOUTH = "south", "South"
    CENTRAL = "central", "Central"
    UNKNOWN = "unknown", "Unknown"


class SourceType(models.TextChoices):
    TELEGRAM = "telegram", "Telegram Channel"
    X = "x", "X (Twitter) Handle"
    RSS = "rss", "RSS Feed"
    GOV = "gov", "Government Site"


class Source(models.Model):
    """A monitored origin of raw signals (Telegram, X, RSS, Gov site)."""

    name = models.CharField(max_length=200)
    source_type = models.CharField(max_length=20, choices=SourceType.choices)
    # Channel handle, RSS/Atom URL, or scrape target.
    identifier = models.CharField(
        max_length=500,
        help_text="Telegram channel/X handle/RSS URL/Gov URL used to fetch data.",
    )
    is_active = models.BooleanField(default=True)
    # Cursor for incremental polling + catch-up after downtime.
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_external_id = models.CharField(
        max_length=255, null=True, blank=True,
        help_text="Last seen item id (e.g. Telegram message id) for de-duplication.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["source_type", "is_active"])]

    def __str__(self):
        return f"{self.get_source_type_display()}: {self.name}"


class AlertStatus(models.TextChoices):
    PENDING = "pending", "Pending Analysis"
    PROCESSING = "processing", "Processing"
    ANALYZED = "analyzed", "Analyzed"
    FAILED = "failed", "Analysis Failed"


class Alert(models.Model):
    """A single ingested item, optionally carrying media, plus AI verdicts."""

    source = models.ForeignKey(
        Source, on_delete=models.CASCADE, related_name="alerts"
    )
    # De-duplication key (e.g. telegram message id, tweet id, rss guid).
    external_id = models.CharField(max_length=255, db_index=True)

    title = models.CharField(max_length=500, blank=True, default="")
    content = models.TextField(blank=True, default="")
    url = models.URLField(max_length=1000, blank=True, default="")

    # --- Multimodal media support ---
    # image_url: remote location as scraped. image_path: locally downloaded copy.
    image_url = models.URLField(max_length=1000, null=True, blank=True)
    image_path = models.ImageField(
        upload_to="alerts/%Y/%m/%d/", null=True, blank=True
    )

    # Raw, unstructured payload from the source for auditing/reprocessing.
    raw_data = models.JSONField(default=dict, blank=True)

    # --- AI (OpenRouter Vision) analysis output ---
    status = models.CharField(
        max_length=20, choices=AlertStatus.choices, default=AlertStatus.PENDING
    )
    is_threat = models.BooleanField(null=True, blank=True)
    region = models.CharField(
        max_length=20, choices=Region.choices, default=Region.UNKNOWN
    )
    threat_severity = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="1 (low) to 10 (critical)."
    )
    visual_summary = models.TextField(
        blank=True, default="",
        help_text="What the model spotted in the image, if any.",
    )
    analysis = models.JSONField(
        default=dict, blank=True, help_text="Full structured model response."
    )
    analyzed_at = models.DateTimeField(null=True, blank=True)

    published_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-published_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["source", "external_id"], name="uniq_source_external_id"
            )
        ]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["region", "is_threat"]),
            models.Index(fields=["-published_at"]),
        ]

    def __str__(self):
        flag = "THREAT" if self.is_threat else "info"
        return f"[{flag}] {self.title or self.content[:50]}"

    @property
    def has_image(self):
        return bool(self.image_path) or bool(self.image_url)


class Metric(models.Model):
    """Rolled-up counters for dashboard tiles (per region / per day)."""

    region = models.CharField(
        max_length=20, choices=Region.choices, default=Region.UNKNOWN
    )
    day = models.DateField()
    total_alerts = models.PositiveIntegerField(default=0)
    threat_alerts = models.PositiveIntegerField(default=0)
    avg_severity = models.FloatField(default=0.0)
    extra = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-day", "region"]
        constraints = [
            models.UniqueConstraint(
                fields=["region", "day"], name="uniq_region_day"
            )
        ]

    def __str__(self):
        return f"{self.get_region_display()} {self.day}: {self.threat_alerts}/{self.total_alerts}"
