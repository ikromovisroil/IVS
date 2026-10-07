from datetime import timedelta
from pathlib import Path
from dotenv import load_dotenv
from django.contrib.messages import constants as message_constants

import shutil
import os

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

WKHTMLTOPDF_PATH = os.getenv("WKHTMLTOPDF_PATH", "")
if not WKHTMLTOPDF_PATH:
    WKHTMLTOPDF_PATH = shutil.which("wkhtmltopdf") or ""

# PDF hosil qilish "dvigateli". Standart - weasyprint (production, Linux, GTK3
# o'rnatilgan). Windowsda GTK3 yo'q bo'lsa, .env'da PDF_ENGINE=wkhtmltopdf
# qo'yib, WKHTMLTOPDF_PATH orqali wkhtmltopdf.exe bilan ishlatish mumkin.
PDF_ENGINE = os.getenv("PDF_ENGINE", "weasyprint")


SITE_BASE_URL = os.getenv("SITE_BASE_URL", "https://report.yatm.uz")
# =========================================================
# HELPERS
# =========================================================
def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


# =========================================================
# CORE
# =========================================================
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY .env faylda topilmadi")

DEBUG = env_bool("DEBUG", False)

ALLOWED_HOSTS = env_list(
    "ALLOWED_HOSTS",
    "127.0.0.1,localhost,report.imv.uz"
)


# =========================================================
# APPLICATIONS
# =========================================================
INSTALLED_APPS = [
    "daphne",
    "channels",

    "jazzmin",
    "csp",
    "django_celery_beat",

    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",

    "corsheaders",
    "django_filters",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "rest_framework.authtoken",   # FIX: oldin vergul yo'qligi sababli "drf_yasg" bilan qo'shilib ketgan edi
    "drf_yasg",                   # FIX: yuqoridagi qatordan ajratildi

    "main.apps.MainConfig",
    "core.apps.CoreConfig",
    "api.apps.ApiConfig",
    "bot.apps.BotConfig",
    "chat.apps.ChatConfig",
    'import_export',
]


# =========================================================
# MIDDLEWARE
# =========================================================
MIDDLEWARE = [
    "csp.middleware.CSPMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",

    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",   # FIX: CommonMiddleware'dan OLDIN bo'lishi kerak
    "django.middleware.common.CommonMiddleware",

    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",

    "core.middlewares.audit.AuditMiddleware",
    "core.middlewares.security_headers.SecurityHeadersMiddleware",
    "api.middleware.ApiGuardMiddleware",   # /api/: X-API-Version, texnik ishlar (503), majburiy yangilash (426)
]


# =========================================================
# URL / WSGI
# =========================================================
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Chat (Django Channels) uchun channel layer. Productionda Redis (Celery
# uchun ishlatilayotgan Redis'dan alohida DB raqami bilan) beriladi:
#   CHANNELS_REDIS_URL=redis://localhost:6379/1
# Lokal rivojlantirishda (Redis shart emas) - xotiradagi layer ishlatiladi,
# lekin u faqat BITTA process ichida ishlaydi (runserver uchun yetarli).
CHANNELS_REDIS_URL = os.getenv("CHANNELS_REDIS_URL", "")
if CHANNELS_REDIS_URL:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [CHANNELS_REDIS_URL]},
        }
    }
else:
    CHANNEL_LAYERS = {
        "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
    }


# =========================================================
# TEMPLATES
# =========================================================
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "main.context_processors.deed_notifications",
                "main.context_processors.order_notifications",
                "main.context_processors.order_receiver_count",
                "main.context_processors.contact_badge_counts",
                "main.context_processors.vapid_context",
                "chat.context_processors.chat_notifications",
            ],
        },
    },
]


# =========================================================
# DATABASE
# =========================================================
USE_POSTGRES = env_bool("USE_POSTGRES", False)

if USE_POSTGRES:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("DB_NAME", ""),
            "USER": os.getenv("DB_USER", ""),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": os.getenv("DB_HOST", "127.0.0.1"),
            "PORT": os.getenv("DB_PORT", "5432"),
            "CONN_MAX_AGE": 60,
            "OPTIONS": {
                "connect_timeout": 10,
            },
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


# =========================================================
# AUTH
# =========================================================
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
]

LOGIN_URL = "/sso/login/"
LOGIN_REDIRECT_URL = "profil"
LOGOUT_REDIRECT_URL = "/sso/login/"


# =========================================================
# MESSAGES FRAMEWORK
# =========================================================
from django.contrib.messages import constants as message_constants
MESSAGE_TAGS = {
    message_constants.ERROR: "danger",
}

# =========================================================
# PASSWORD VALIDATION
# =========================================================
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"
    },
]


# =========================================================
# INTERNATIONALIZATION
# =========================================================
LANGUAGE_CODE = "uz"
TIME_ZONE = "Asia/Tashkent"
USE_I18N = True
USE_TZ = True


# =========================================================
# STATIC / MEDIA
# =========================================================
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
# O'chirilgan chat fayllari ochiq MEDIA_ROOT'dan tashqariga (internetdan ochib bo'lmaydigan joyga) ko'chiriladi
CHAT_PRIVATE_ROOT = BASE_DIR / "media_private" / "chat_deleted"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# =========================================================
# SESSION / COOKIE
# =========================================================
SESSION_COOKIE_AGE = 60 * 60 * 6
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Lax"


# =========================================================
# REST FRAMEWORK
# =========================================================
REST_FRAMEWORK = {
    # JWT birinchi: tokensiz/eskirgan so'rovga 401 (+ WWW-Authenticate: Bearer) qaytadi — mobil ilova shu bilan
    # tokenni yangilash vaqtini biladi. (Birinchi sessiya bo'lsa DRF hamma autentifikatsiya xatosini 403 qilardi.)
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "api.authentication.AuditJWTAuthentication",   # JWT + audit jurnali (api/authentication.py)
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    # So'rovlar chegarasi (suiiste'mol va brute-force dan himoya); ilova uchun yetarlicha keng
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {"user": "1200/min"},
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    'DEFAULT_PAGINATION_CLASS': 'api.pagination.StandardResultsPagination',
    'PAGE_SIZE': 20,
}


# =========================================================
# FCM (Android push): service account JSON fayl yo'li; bo'sh bo'lsa FCM o'chiq
# =========================================================
FIREBASE_CREDENTIALS_FILE = os.getenv("FIREBASE_CREDENTIALS_FILE", "")
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "")


# =========================================================
# Mobil ilova: majburiy yangilash va texnik ishlar (api/app_views.py)
# =========================================================
ANDROID_MIN_VERSION = os.getenv("ANDROID_MIN_VERSION", "")        # shundan eski versiya ishlay olmaydi (426)
ANDROID_LATEST_VERSION = os.getenv("ANDROID_LATEST_VERSION", "")  # mavjud eng yangi versiya
ANDROID_UPDATE_URL = os.getenv("ANDROID_UPDATE_URL", "")          # yangilash havolasi (Play Market va h.k.)
ANDROID_UPDATE_MESSAGE = os.getenv("ANDROID_UPDATE_MESSAGE", "")
API_MAINTENANCE = os.getenv("API_MAINTENANCE", "0") == "1"        # 1 — barcha /api/ so'rovlar 503
API_MAINTENANCE_MESSAGE = os.getenv("API_MAINTENANCE_MESSAGE", "")


# =========================================================
# SWAGGER (API hujjatlari): standart holatda faqat tizimga kirganlar uchun; SWAGGER_PUBLIC=1 — hamma uchun
# =========================================================
SWAGGER_PUBLIC = os.getenv("SWAGGER_PUBLIC", "0") == "1"


# =========================================================
# JWT
# =========================================================
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}


# =========================================================
# SWAGGER
# =========================================================
SWAGGER_SETTINGS = {
    "USE_SESSION_AUTH": False,
    "SECURITY_DEFINITIONS": {
        "Bearer": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
            "description": "Format: Bearer <access_token>",
        }
    },
}


# =========================================================
# CORS / CSRF
# =========================================================
CORS_ALLOW_ALL_ORIGINS = False

if DEBUG:
    CORS_ALLOWED_ORIGINS = [
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ]
    CSRF_TRUSTED_ORIGINS = [
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ]
else:
    CORS_ALLOWED_ORIGINS = env_list(
        "CORS_ALLOWED_ORIGINS",
        "https://report.imv.uz"
    )
    CSRF_TRUSTED_ORIGINS = env_list(
        "CSRF_TRUSTED_ORIGINS",
        "https://report.imv.uz"
    )

CORS_ALLOW_CREDENTIALS = True

# =========================================================
# SSO
# =========================================================
SSO_CLIENT_ID = os.getenv("SSO_CLIENT_ID")
SSO_CLIENT_SECRET = os.getenv("SSO_CLIENT_SECRET")
SSO_AUTH_URL = os.getenv("SSO_AUTH_URL")
SSO_TOKEN_URL = os.getenv("SSO_TOKEN_URL")
SSO_EIMZO_SIGN_URL = os.getenv("SSO_EIMZO_SIGN_URL")
SSO_REDIRECT_URI = os.getenv("SSO_REDIRECT_URI")
# Android ilovaning SSO redirect_uri lari (vergul bilan). Bo'sh bo'lsa /api/auth/sso/token/ o'chiq.
MOBILE_SSO_REDIRECT_URIS = [x.strip() for x in os.getenv("MOBILE_SSO_REDIRECT_URIS", "").split(",") if x.strip()]
EIMZO_RETURN_URL = os.getenv("EIMZO_RETURN_URL")
# Imzolash sessiyasi amal qilish muddati (soniya) va qaytishda `doc` majburiyligi (provayder qaytarishi tasdiqlangach "1" qiling)
EIMZO_PENDING_TTL = int(os.getenv("EIMZO_PENDING_TTL", "900"))
EIMZO_REQUIRE_DOC = os.getenv("EIMZO_REQUIRE_DOC", "0") == "1"

GATEWAY_BASE_URL = os.getenv("GATEWAY_BASE_URL")
GATEWAY_USERNAME = os.getenv("GATEWAY_USERNAME")
GATEWAY_PASSWORD = os.getenv("GATEWAY_PASSWORD")

# =========================================================
# LOGGING
# =========================================================
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "file": {
            "level": "ERROR",
            "class": "logging.FileHandler",
            "filename": LOG_DIR / "error.log",
            "formatter": "verbose",
        },
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}


# =========================================================
# SECURITY
# =========================================================
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_RESOURCE_POLICY = "same-origin"

if DEBUG:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False

    SECURE_HSTS_SECONDS = 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False

    SECURE_PROXY_SSL_HEADER = None
    USE_X_FORWARDED_HOST = False

    SECURE_REDIRECT_EXEMPT = []
else:
    SECURE_SSL_REDIRECT = True

    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    CSRF_COOKIE_SAMESITE = "Lax"
    CSRF_COOKIE_HTTPONLY = False

    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = True

    SECURE_REDIRECT_EXEMPT = []



# =========================================================
# FILE UPLOAD LIMITS
# =========================================================
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

# =========================================================
# CELERY
# =========================================================
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "Asia/Tashkent"
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# =========================================================
# CSP (django-csp 4.0+)
# =========================================================
# ESLATMA: bu REPORT_ONLY rejimda ishlaydi (hech narsani bloklamaydi, faqat
# hisobot beradi). Productionda real himoya kerak bo'lsa, quyidagini
# CONTENT_SECURITY_POLICY nomi bilan (REPORT_ONLY'siz) alohida qo'shing,
# va "report-uri"/"report-to" ni ham belgilang, aks holda hisobotlar
# hech qayerga yubormaydi.
CONTENT_SECURITY_POLICY_REPORT_ONLY = {
    "INCLUDE_NONCE_IN": ["script-src", "style-src"],
    "DIRECTIVES": {
        "default-src": ["'self'"],
        "script-src": [
            "'self'",
            "https://cdn.jsdelivr.net",
            "https://code.jquery.com",
            "https://cdnjs.cloudflare.com",
            "https://fonts.googleapis.com",
        ],
        "style-src": [
            "'self'",
            "https://fonts.googleapis.com",
            "https://cdn.jsdelivr.net",
            "https://cdnjs.cloudflare.com",
        ],
        "font-src": [
            "'self'",
            "https://fonts.gstatic.com",
            "https://cdn.jsdelivr.net",
            "https://cdnjs.cloudflare.com",
        ],
        "img-src": [
            "'self'",
            "data:",
            "blob:",
        ],
        "connect-src": ["'self'"],
        "object-src":  ["'none'"],
        "base-uri":    ["'self'"],
        "frame-ancestors": ["'none'"],
    },
}

JAZZMIN_SETTINGS = {
    "site_title": "Admin Panel",
    "site_header": "Boshqaruv paneli",
    "site_brand": "IVC Service",
    "site_logo": None,
    "login_logo": None,
    "site_icon": None,
    "welcome_sign": "Xush kelibsiz",
    "copyright": "IVC Service",
    "search_model": [],
    "user_avatar": None,

    "topmenu_links": [
        {"name": "Bosh sahifa", "url": "admin:index", "permissions": ["auth.view_user"]},
    ],

    "usermenu_links": [],

    "show_sidebar": True,
    "navigation_expanded": True,
    "hide_apps": [],
    "hide_models": [],
    "order_with_respect_to": [],

    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",
    },
    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",

    "related_modal_active": False,
    "custom_css": None,
    "custom_js": None,
    "use_google_fonts_cdn": True,
    "show_ui_builder": False,
    "changeform_format": "horizontal_tabs",
    "changeform_format_overrides": {},
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": False,
    "accent": "accent-primary",
    "navbar": "navbar-white navbar-light",
    "no_navbar_border": False,
    "navbar_fixed": False,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": False,
    "sidebar": "sidebar-dark-primary",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": False,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "theme": "default",
    "default_theme_mode": "light",
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success",
    },
}


VAPID_PRIVATE_KEY_PEM = str(BASE_DIR / "private_key.pem")

VAPID_PUBLIC_KEY = "BDG3vD4zmf8dNsRQRIoqebQKCn_QeJTwiUCO1pJWVoV_SKgOhFVEOX7bPagYoQwBSijel8Nf8q1DrqS7uydo5No"

VAPID_CLAIMS = {
    "sub": "mailto:admin@yatm.uz"
}