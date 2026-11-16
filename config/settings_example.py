"""Configuración privada de SICSI.

Copie settings_example.py como settings.py y edite los valores en su PC.
settings.py está excluido de Git para proteger contraseñas y SECRET_KEY.
"""
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# Genere una clave propia con secrets.token_urlsafe(48).
SECRET_KEY = ""
if len(SECRET_KEY) < 40:
    raise ImproperlyConfigured("Configure SECRET_KEY en config/settings.py con una clave aleatoria de al menos 40 caracteres.")

# Desarrollo local. Antes de publicar revise docs/DESPLIEGUE.md.
DEBUG = True
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]
TRUST_PROXY_HTTPS = False

INSTALLED_APPS = ["django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles", "core.apps.CoreConfig"]
MIDDLEWARE = ["django.middleware.security.SecurityMiddleware", "django.contrib.sessions.middleware.SessionMiddleware", "django.middleware.common.CommonMiddleware", "django.middleware.csrf.CsrfViewMiddleware", "django.contrib.auth.middleware.AuthenticationMiddleware", "core.middleware.PrivateResponseMiddleware", "django.contrib.messages.middleware.MessageMiddleware", "django.middleware.clickjacking.XFrameOptionsMiddleware"]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [BASE_DIR / "templates"], "APP_DIRS": True, "OPTIONS": {"context_processors": ["django.template.context_processors.request", "django.contrib.auth.context_processors.auth", "django.contrib.messages.context_processors.messages"]}}]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
# Complete USER y PASSWORD con los datos de su PostgreSQL local.
# NAME es la base; USER es el rol de PostgreSQL, no el usuario de acceso a SICSI.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "sicsi",
        "USER": "sicsi",
        "PASSWORD": "",
        "HOST": "127.0.0.1",
        "PORT": "5432",
        "CONN_MAX_AGE": 60,
        "OPTIONS": {"sslmode": "prefer"},
    }
}

AUTH_USER_MODEL = "core.Usuario"
AUTH_PASSWORD_VALIDATORS = [{"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"}, {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 14}}, {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"}, {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"}]
PASSWORD_HASHERS = ["django.contrib.auth.hashers.Argon2PasswordHasher", "django.contrib.auth.hashers.PBKDF2PasswordHasher"]
LANGUAGE_CODE = "es-gt"
TIME_ZONE = "America/Guatemala"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
PRIVATE_MEDIA_ROOT = BASE_DIR / "private_media"
if not PRIVATE_MEDIA_ROOT.is_absolute():
    PRIVATE_MEDIA_ROOT = BASE_DIR / PRIVATE_MEDIA_ROOT
# No se añade ninguna ruta pública para estos documentos.
MEDIA_ROOT = PRIVATE_MEDIA_ROOT
MEDIA_URL = "/documentos-no-publicos/"
FILE_UPLOAD_PERMISSIONS = 0o600
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o700
FILE_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 256 * 1024
UPLOAD_MAX_MB = 10
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"
SESSION_COOKIE_NAME = "sicsi_session"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"
SESSION_COOKIE_AGE = 8 * 60 * 60
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SAMESITE = "Strict"
CSRF_TRUSTED_ORIGINS = []
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
if TRUST_PROXY_HTTPS:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
APP_URL = "http://127.0.0.1:8000".rstrip("/")
EMAIL_MODE = "console"  # "smtp" para enviar correos reales.
if not DEBUG and EMAIL_MODE != "smtp":
    raise ImproperlyConfigured("En producción EMAIL_MODE debe ser smtp.")
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend" if EMAIL_MODE == "smtp" else "django.core.mail.backends.console.EmailBackend"
EMAIL_HOST = ""
EMAIL_PORT = 587
EMAIL_HOST_USER = ""
EMAIL_HOST_PASSWORD = ""
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False
EMAIL_TIMEOUT = 30
DEFAULT_FROM_EMAIL = ""
if EMAIL_USE_SSL and EMAIL_USE_TLS:
    raise ImproperlyConfigured("EMAIL_USE_TLS y EMAIL_USE_SSL no pueden estar activos a la vez.")
BACKUP_DIR = BASE_DIR / "backups"
if not BACKUP_DIR.is_absolute():
    BACKUP_DIR = BASE_DIR / BACKUP_DIR
PG_DUMP_BIN = "pg_dump"  # En Windows puede usar la ruta completa a pg_dump.exe.
