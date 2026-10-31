"""
Settings for the FleetFlow backend API. Everything that differs between environments
comes from environment variables (or a local `.env` file); see `.env.example`.
"""

import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env(name, default=None):
    """An environment variable; empty values (`FOO=` in .env) count as unset."""
    value = os.environ.get(name, "").strip()
    return value or default


def env_bool(name, default=False):
    value = env(name)
    return default if value is None else value.lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [item.strip() for item in (env(name) or default).split(",") if item.strip()]


DEBUG = env_bool("DEBUG")

SECRET_KEY = env("SECRET_KEY") or ("insecure-dev-key-change-me" if DEBUG else None)
if not SECRET_KEY:
    raise ImproperlyConfigured("Set SECRET_KEY (or DEBUG=true for local development).")

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1" if DEBUG else "")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "core",
    "accounts",
    "bookings",
    "content",
]

MIDDLEWARE = [
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
WSGI_APPLICATION = "config.wsgi.application"

# The API paths have no trailing slash (`/v1/bookings`), exactly as the frontend calls them.
APPEND_SLASH = False

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# SQLite for local development; set DATABASE_URL (e.g. postgres://…) in production.
DATABASES = {
    "default": dj_database_url.parse(
        env("DATABASE_URL", f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# Rate limits are counted in the cache. Use Redis when there is more than one worker process.
if env("REDIS_URL"):
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": env("REDIS_URL")}}
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en"
# Booking dates and times are Polish local time, so "today" is always computed in this zone.
TIME_ZONE = "Europe/Warsaw"
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Uploaded images. Locally they are stored in MEDIA_ROOT and served by Django; set S3_BUCKET
# to store them in S3 (or any S3-compatible service such as Cloudflare R2) instead.
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(env("MEDIA_ROOT", BASE_DIR / "media"))

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
if env("S3_BUCKET"):
    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": env("S3_BUCKET"),
            "region_name": env("S3_REGION"),
            "endpoint_url": env("S3_ENDPOINT_URL"),
            "custom_domain": env("S3_CUSTOM_DOMAIN"),
            "querystring_auth": False,
            "file_overwrite": False,
            "default_acl": env("S3_DEFAULT_ACL"),
        },
    }
SERVE_MEDIA = env_bool("SERVE_MEDIA", not env("S3_BUCKET"))

# Public URL of this API server, used to build absolute links to uploaded images,
# e.g. https://api.fleetflowservice.com. Defaults to the host of the upload request.
PUBLIC_BASE_URL = (env("PUBLIC_BASE_URL") or "").rstrip("/")

# Images are at most 3.5 MB; leave room for the multipart envelope.
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["core.authentication.BearerTokenAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "EXCEPTION_HANDLER": "core.exceptions.exception_handler",
    "DEFAULT_THROTTLE_RATES": {
        "bookings": env("THROTTLE_BOOKINGS", "10/hour"),
        "contact": env("THROTTLE_CONTACT", "10/hour"),
        "enquiries": env("THROTTLE_ENQUIRIES", "10/hour"),
        "login": env("THROTTLE_LOGIN", "20/hour"),
    },
    # Number of reverse proxies in front of the API (used to read the client IP from X-Forwarded-For).
    "NUM_PROXIES": int(env("NUM_PROXIES")) if env("NUM_PROXIES") else None,
}

# Admin sign-in tokens last this long (the frontend keeps its cookie for the same time).
AUTH_TOKEN_TTL_SECONDS = int(env("AUTH_TOKEN_TTL_SECONDS", 8 * 3600))

# Shared secret between the Next.js server and this API. When the frontend sends it in
# `X-Api-Key`, the API trusts its `X-Visitor-Ip` header and rate-limits each visitor
# separately. Without it, every visitor shares the Next.js server's limit.
FRONTEND_API_KEY = env("FRONTEND_API_KEY", "")

# Email. The API sends every email the website needs (see bookings/emails.py):
# - with RESEND_API_KEY, through Resend's HTTP API;
# - otherwise with EMAIL_HOST, through SMTP;
# - otherwise they are printed to the console (development).
RESEND_API_KEY = env("RESEND_API_KEY", "")
if RESEND_API_KEY:
    EMAIL_BACKEND = "core.mail.ResendEmailBackend"
elif env("EMAIL_HOST"):
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST", "localhost")
EMAIL_PORT = int(env("EMAIL_PORT", 587))
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", False)
EMAIL_TIMEOUT = 15
# Must be on a domain verified with your email provider (SPF/DKIM).
DEFAULT_FROM_EMAIL = env("EMAIL_FROM", "FleetFlow <noreply@fleetflowservice.com>")
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# Where team notifications go (comma-separated): new bookings, messages, quotes and applications.
TEAM_EMAILS = env_list("NOTIFY_EMAIL", "operations@fleetflowservice.com")
# Public URL of the website, for "Open the admin" links in team emails.
SITE_URL = env("SITE_URL", "https://fleetflowservice.com").rstrip("/")
# Taxi customers get no email by default: the team confirms each ride personally.
SEND_BOOKING_CONFIRMATION = env_bool("SEND_BOOKING_CONFIRMATION", False)
COMPANY_PHONE = env("COMPANY_PHONE", "+48 453 505 286")
COMPANY_REPLY_TO = env("COMPANY_REPLY_TO", "")
# FleetFlow Cargo's contact details, shown in the cargo quote confirmation.
CARGO_WHATSAPP = env("CARGO_WHATSAPP", "+48 516 684 320")
CARGO_EMAIL = env("CARGO_EMAIL", "operations@fleetflowservice.com")

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
    SECURE_REDIRECT_EXEMPT = [r"^v1/health$"]
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(env("SECURE_HSTS_SECONDS", 60 * 60 * 24 * 30))
    SECURE_CONTENT_TYPE_NOSNIFF = True

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
}
