import smtplib
from django.conf import settings
from django.core.mail import EmailMessage, get_connection
from django.core.mail.backends.smtp import EmailBackend

class CapturaRespuesta:
    def data(self, msg):
        result = super().data(msg)
        self.respuesta_data = result
        return result

class SMTPConRespuesta(CapturaRespuesta, smtplib.SMTP):
    pass

class SMTPSSLConRespuesta(CapturaRespuesta, smtplib.SMTP_SSL):
    pass

class BackendSMTP(EmailBackend):
    @property
    def connection_class(self):
        return SMTPSSLConRespuesta if self.use_ssl else SMTPConRespuesta

def entregar(asunto, texto, destinatario):
    if settings.EMAIL_MODE == "smtp" and (not settings.EMAIL_HOST or not settings.DEFAULT_FROM_EMAIL):
        raise ValueError("Configure SMTP_HOST y SMTP_FROM antes de enviar alertas.")
    backend = BackendSMTP() if settings.EMAIL_MODE == "smtp" else get_connection()
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
