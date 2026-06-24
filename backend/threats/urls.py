from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

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
    # JWT auth endpoints.
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("summary/", DashboardSummaryView.as_view(), name="dashboard-summary"),
    path("", include(router.urls)),
]
