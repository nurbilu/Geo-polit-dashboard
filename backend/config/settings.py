"""
Django settings for the Geopolitical & Security Threat Dashboard.

Tuned for a low-memory, start/stop lifecycle:
- Standard WSGI (no ASGI/WebSocket overhead).
- MySQL 8 with a JSON column for raw payloads.
- Celery + Redis for async multimodal analysis.
"""
import os
import sys
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

if sys.platform.startswith("win"):
    # Allow Django's MySQL backend to run on Windows without compiling mysqlclient.
    import pymysql

    pymysql.install_as_MySQLdb()

BASE_DIR = Path(__file__).resolve().parent.parent
# Load root-level .env for local (non-Docker) Windows runs.
load_dotenv(BASE_DIR.parent / ".env")


def env(key, default=None):
    return os.environ.get(key, default)


def env_bool(key, default=False):
    return str(os.environ.get(key, default)).lower() in ("1", "true", "yes", "on")


def env_list(key, default=""):
    raw = os.environ.get(key, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


# --- Core ---------------------------------------------------------------
SECRET_KEY = env("DJANGO_SECRET_KEY", "insecure-dev-key-change-me")
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,web")
CSRF_TRUSTED_ORIGINS = env_list(
    "DJANGO_CSRF_TRUSTED_ORIGINS", "http://localhost:4200,http://localhost:8000"
)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party
    "rest_framework",
    "django_filters",
    "corsheaders",
    # Local
    "threats",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# --- Database (MySQL 8) -------------------------------------------------
default_mysql_host = "127.0.0.1" if sys.platform.startswith("win") else "db"
mysql_host = env("MYSQL_HOST", default_mysql_host)
# In Docker, `db` is valid; in local Windows shells it is not resolvable.
if sys.platform.startswith("win") and mysql_host == "db":
    mysql_host = "127.0.0.1"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": env("MYSQL_DATABASE", "threats"),
        "USER": env("MYSQL_USER", "threats"),
        "PASSWORD": env("MYSQL_PASSWORD", "threats_pass"),
        "HOST": mysql_host,
        "PORT": env("MYSQL_PORT", "3306"),
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
        "CONN_MAX_AGE": 60,
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- I18N ---------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Jerusalem"
USE_I18N = True
USE_TZ = True

# --- Static & media -----------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- DRF ----------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
        "rest_framework.filters.SearchFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.LimitOffsetPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    # JWT first, then session (for the browsable API / admin). Default
    # permission stays open so the Angular polling feed keeps working; protect
    # individual viewsets/actions with IsAuthenticated where needed.
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
}

# --- JWT (djangorestframework-simplejwt) -------------------------------
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=int(env("JWT_ACCESS_MINUTES", "60"))
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=int(env("JWT_REFRESH_DAYS", "7"))
    ),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": False,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "SIGNING_KEY": SECRET_KEY,
}

# --- CORS (Angular dev/prod) -------------------------------------------
CORS_ALLOWED_ORIGINS = env_list(
    "DJANGO_CSRF_TRUSTED_ORIGINS", "http://localhost:4200,http://localhost:8000"
)
CORS_ALLOW_CREDENTIALS = True

# --- Celery / Redis -----------------------------------------------------
CELERY_BROKER_URL = env("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", "redis://redis:6379/1")
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # Keep memory predictable for heavy AI tasks.
CELERY_RESULT_EXPIRES = timedelta(hours=6)
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# Periodic schedule. The startup catch-up runs via a signal (see threats/apps.py).
SOURCE_POLL_INTERVAL = int(env("SOURCE_POLL_INTERVAL", "120"))
CELERY_BEAT_SCHEDULE = {
    "poll-sources": {
        "task": "threats.tasks.poll_all_sources",
        "schedule": float(SOURCE_POLL_INTERVAL),
    },
}

# --- AI analysis provider ----------------------------------------------
# "groq" (Llama 4 Scout via Groq Cloud) or "openrouter" (hosted vision model).
AI_PROVIDER = env("AI_PROVIDER", "groq").strip().lower()

# Groq Cloud (OpenAI-compatible API) running Llama 4 Scout.
GROQ_API_KEY = env("GROQ_API_KEY", "")
GROQ_MODEL = env("GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
GROQ_BASE_URL = env("GROQ_BASE_URL", "https://api.groq.com/openai/v1")

# OpenRouter (legacy / fallback hosted vision model).
OPENROUTER_API_KEY = env("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = env("OPENROUTER_MODEL", "meta-llama/llama-3.2-11b-vision-instruct")

# --- Auth / registration ------------------------------------------------
# Shared secret that gates self-service admin (superuser) registration from the
# frontend. Keep this out of source control; supply it via .env.
AUTH_ADMIN_PWD = env("AUTH_ADMIN_PWD", "")

# --- App-specific -------------------------------------------------------
CATCHUP_WINDOW_HOURS = int(env("CATCHUP_WINDOW_HOURS", "24"))

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "[{levelname}] {asctime} {name}: {message}", "style": "{"}
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"}
    },
    "root": {"handlers": ["console"], "level": env("DJANGO_LOG_LEVEL", "INFO")},
}
