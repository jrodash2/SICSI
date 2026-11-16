"""Backend SMTP de SICSI: TLS de Django y captura de la respuesta DATA."""
import smtplib
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

class CustomEmailBackend(EmailBackend):
    @property
    def connection_class(self):
        return SMTPSSLConRespuesta if self.use_ssl else SMTPConRespuesta
