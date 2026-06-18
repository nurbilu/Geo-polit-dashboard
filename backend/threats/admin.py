from django.contrib import admin
from django.utils.html import format_html

from .models import Alert, Metric, Source


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = (
        "name", "source_type", "identifier", "is_active",
        "last_synced_at", "last_external_id",
    )
    list_filter = ("source_type", "is_active")
    search_fields = ("name", "identifier")
    list_editable = ("is_active",)


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = (
        "id", "short_title", "source", "status", "is_threat",
        "region", "threat_severity", "thumb", "published_at",
    )
    list_filter = ("status", "is_threat", "region", "source__source_type")
    search_fields = ("title", "content", "external_id", "visual_summary")
    readonly_fields = ("preview", "raw_data", "analysis", "analyzed_at", "created_at")
    date_hierarchy = "published_at"
    actions = ["requeue_analysis"]

    @admin.display(description="Title")
    def short_title(self, obj):
        return (obj.title or obj.content[:60]) or f"Alert #{obj.id}"

    @admin.display(description="Image")
    def thumb(self, obj):
        src = (obj.image_path.url if obj.image_path else None) or obj.image_url
        if not src:
            return "—"
        return format_html(
            '<img src="{}" style="height:40px;border-radius:4px;" />', src
        )

    @admin.display(description="Preview")
    def preview(self, obj):
        src = (obj.image_path.url if obj.image_path else None) or obj.image_url
        if not src:
            return "No image"
        return format_html(
            '<img src="{}" style="max-height:300px;border-radius:8px;" />', src
        )

    @admin.action(description="Re-queue selected alerts for Llama 4 analysis")
    def requeue_analysis(self, request, queryset):
        from .tasks import analyze_alert

        count = 0
        for alert in queryset:
            analyze_alert.delay(alert.id)
            count += 1
        self.message_user(request, f"Re-queued {count} alert(s) for analysis.")


@admin.register(Metric)
class MetricAdmin(admin.ModelAdmin):
    list_display = (
        "day", "region", "total_alerts", "threat_alerts", "avg_severity",
    )
    list_filter = ("region",)
    date_hierarchy = "day"
