from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AlertViewSet,
    DashboardSummaryView,
    MetricViewSet,
    SourceViewSet,
)

router = DefaultRouter()
router.register(r"sources", SourceViewSet, basename="source")
router.register(r"alerts", AlertViewSet, basename="alert")
router.register(r"metrics", MetricViewSet, basename="metric")

urlpatterns = [
    path("summary/", DashboardSummaryView.as_view(), name="dashboard-summary"),
    path("", include(router.urls)),
]
