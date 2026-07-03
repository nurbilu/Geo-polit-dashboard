from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Alert, Metric, Source

User = get_user_model()


class RegisterSerializer(serializers.Serializer):
    """
    Self-service registration. Regular users are created as-is; admin
    registration additionally requires the shared `AUTH_ADMIN_PWD` secret via
    the `admin_verification_password` field.
    """

    username = serializers.CharField(max_length=150)
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    password = serializers.CharField(write_only=True, min_length=8)
    is_admin = serializers.BooleanField(default=False)
    admin_verification_password = serializers.CharField(
        write_only=True, required=False, allow_blank=True, default=""
    )

    def validate_username(self, value):
        value = value.strip()
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("This username is already taken.")
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    def admin_code_ok(self) -> bool:
        """Whether the supplied admin verification code matches the secret."""
        configured = settings.AUTH_ADMIN_PWD
        supplied = self.validated_data.get("admin_verification_password") or ""
        return bool(configured) and supplied == configured

    def create(self, validated_data):
        is_admin = validated_data.get("is_admin", False)
        username = validated_data["username"]
        email = validated_data.get("email", "")
        password = validated_data["password"]

        if is_admin:
            user = User.objects.create_superuser(
                username=username, email=email, password=password
            )
        else:
            # create_user hashes the password via the user manager.
            user = User.objects.create_user(
                username=username, email=email, password=password
            )
        return user


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
    country_display = serializers.CharField(source="get_country_display", read_only=True)
    region_display = serializers.CharField(source="get_region_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    image = serializers.SerializerMethodField()
    has_image = serializers.BooleanField(read_only=True)
    is_primary = serializers.BooleanField(read_only=True)

    class Meta:
        model = Alert
        fields = [
            "id", "source", "source_name", "source_type", "external_id",
            "title", "content", "url", "image", "image_url", "has_image",
            "status", "status_display", "is_threat",
            "country", "country_display", "region", "region_display",
            "threat_severity", "visual_summary", "summary_hebrew", "analysis",
            "parent_alert", "cluster_count", "is_primary",
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
