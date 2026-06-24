from datetime import timedelta

from django.db.models import Avg, Count, Q
from django.utils import timezone
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Alert, Metric, Source
from .serializers import AlertSerializer, MetricSerializer, SourceSerializer


class SourceViewSet(viewsets.ModelViewSet):
    """
    Full CRUD for monitored sources. Reads are public (the dashboard polls
    them); create/update/delete require a valid JWT (the nurADMIN console).
    """

    queryset = Source.objects.all()
    serializer_class = SourceSerializer
    filterset_fields = ["source_type", "is_active"]
    search_fields = ["name", "identifier"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permission() for permission in self.permission_classes]
        return [IsAuthenticated()]


class AlertViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """
    Live feed endpoint consumed by the Angular polling service.

    Supports filtering by region, threat flag, severity, source type, and a
    `since` timestamp so the frontend can fetch only fresh items.
    """

    serializer_class = AlertSerializer
    filterset_fields = ["region", "is_threat", "status", "source__source_type"]
    search_fields = ["title", "content", "visual_summary"]
    ordering_fields = ["published_at", "threat_severity", "created_at"]

    def get_queryset(self):
        qs = Alert.objects.select_related("source").all()
        params = self.request.query_params

        since = params.get("since")
        if since:
            qs = qs.filter(published_at__gt=since)

        min_sev = params.get("min_severity")
        if min_sev and min_sev.isdigit():
            qs = qs.filter(threat_severity__gte=int(min_sev))

        only_with_image = params.get("has_image")
        if only_with_image in ("1", "true", "True"):
            qs = qs.filter(Q(image_path__gt="") | Q(image_url__isnull=False))

        return qs


class MetricViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Metric.objects.all()
    serializer_class = MetricSerializer
    filterset_fields = ["region", "day"]


class DashboardSummaryView(APIView):
    """Aggregated KPIs for the dashboard header tiles."""

    def get(self, request):
        window_hours = int(request.query_params.get("hours", 24))
        since = timezone.now() - timedelta(hours=window_hours)
        recent = Alert.objects.filter(published_at__gte=since)

        by_region = (
            recent.filter(is_threat=True)
            .values("region")
            .annotate(count=Count("id"), avg_severity=Avg("threat_severity"))
            .order_by("-count")
        )

        return Response(
            {
                "window_hours": window_hours,
                "total_alerts": recent.count(),
                "threat_alerts": recent.filter(is_threat=True).count(),
                "pending_analysis": Alert.objects.filter(status="pending").count(),
                "critical_alerts": recent.filter(threat_severity__gte=8).count(),
                "by_region": list(by_region),
            }
        )
