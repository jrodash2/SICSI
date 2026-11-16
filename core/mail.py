from django.conf import settings
from django.core.mail import EmailMessage, get_connection
from .email_backend import CustomEmailBackend

# Compatibilidad con instalaciones que utilizaban el nombre anterior.
BackendSMTP = CustomEmailBackend

def respuesta_segura(exc):
    respuesta = f"{type(exc).__name__}: {exc}"
    for secreto in [settings.EMAIL_HOST_PASSWORD, settings.DATABASES["default"].get("PASSWORD", ""), settings.SECRET_KEY]:
        if secreto:
            respuesta = respuesta.replace(secreto, "[oculto]")
    return respuesta[:4000]

def entregar(asunto, texto, destinatario):
    if settings.EMAIL_MODE == "smtp" and (not settings.EMAIL_HOST or not settings.DEFAULT_FROM_EMAIL):
        raise ValueError("Configure EMAIL_HOST y DEFAULT_FROM_EMAIL en settings.py antes de enviar alertas.")
    # El SMTP estándar de versiones previas se actualiza sin perder el registro DATA.
    backend_path = settings.EMAIL_BACKEND
    if settings.EMAIL_MODE == "smtp" and backend_path == "django.core.mail.backends.smtp.EmailBackend":
        backend_path = "core.email_backend.CustomEmailBackend"
    backend = get_connection(backend=backend_path)
    backend.open()
    try:
        connection = getattr(backend, "connection", None)
        count = EmailMessage(asunto, texto, settings.DEFAULT_FROM_EMAIL or "sicsi@localhost", [destinatario], connection=backend).send()
        if count != 1:
            raise RuntimeError("El backend no confirmó el envío del mensaje.")
        if settings.EMAIL_MODE != "smtp":
            return "Simulada", "Modo de desarrollo: mensaje generado sin envío SMTP real."
        code, response = getattr(connection, "respuesta_data", (None, b"Sin respuesta DATA"))
        if code is None:
            raise RuntimeError("No se pudo registrar la respuesta DATA de SMTP.")
        return "Enviada", f"{code} {response.decode('utf-8', errors='replace')}"
    finally:
        backend.close()
