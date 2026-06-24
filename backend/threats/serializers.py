from rest_framework import serializers

from .models import Alert, Metric, Source


class SourceSerializer(serializers.ModelSerializer):
    source_type_display = serializers.CharField(
        source="get_source_type_display", read_only=True
    )

    class Meta:
        model = Source
        fields = [
            "id", "name", "source_type", "source_type_display", "identifier",
            "is_active", "last_synced_at", "created_at",
        ]


class AlertSerializer(serializers.ModelSerializer):
    source_name = serializers.CharField(source="source.name", read_only=True)
    source_type = serializers.CharField(source="source.source_type", read_only=True)
    region_display = serializers.CharField(source="get_region_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    image = serializers.SerializerMethodField()
    has_image = serializers.BooleanField(read_only=True)

    class Meta:
        model = Alert
        fields = [
            "id", "source", "source_name", "source_type", "external_id",
            "title", "content", "url", "image", "image_url", "has_image",
            "status", "status_display", "is_threat", "region", "region_display",
            "threat_severity", "visual_summary", "summary_hebrew", "analysis",
            "published_at", "analyzed_at", "created_at",
        ]

    def get_image(self, obj):
        """Prefer the locally downloaded copy; fall back to the scraped URL."""
        request = self.context.get("request")
        if obj.image_path:
            url = obj.image_path.url
            return request.build_absolute_uri(url) if request else url
        return obj.image_url or None


class MetricSerializer(serializers.ModelSerializer):
    region_display = serializers.CharField(source="get_region_display", read_only=True)

    class Meta:
        model = Metric
        fields = [
            "id", "region", "region_display", "day", "total_alerts",
            "threat_alerts", "avg_severity", "extra",
        ]
