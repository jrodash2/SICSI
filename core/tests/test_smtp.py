import socketserver
import threading
from django.test import SimpleTestCase, override_settings
from core.mail import entregar

class SMTPPrueba(socketserver.StreamRequestHandler):
    def handle(self):
        self.wfile.write(b"220 localhost prueba\r\n")
        while line := self.rfile.readline():
            command = line.strip().upper()
            if command.startswith(b"EHLO") or command.startswith(b"HELO"):
                self.wfile.write(b"250-localhost\r\n250 SIZE 100000\r\n")
            elif command == b"DATA":
                self.wfile.write(b"354 Fin con punto\r\n")
                while body := self.rfile.readline():
                    if body == b".\r\n":
                        break
                self.wfile.write(b"250 queued as test-001\r\n")
            elif command == b"QUIT":
                self.wfile.write(b"221 Adios\r\n")
                break
            else:
                self.wfile.write(b"250 OK\r\n")

class SMTPTests(SimpleTestCase):
    def test_captura_respuesta_real_de_data_en_smtp_local(self):
        with socketserver.TCPServer(("127.0.0.1", 0), SMTPPrueba) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with override_settings(EMAIL_MODE="smtp", EMAIL_HOST="127.0.0.1", EMAIL_PORT=server.server_address[1], EMAIL_USE_TLS=False, EMAIL_USE_SSL=False, EMAIL_HOST_USER="", EMAIL_HOST_PASSWORD="", DEFAULT_FROM_EMAIL="sicsi@example.test"):
                    estado, respuesta = entregar("Prueba local", "Mensaje sin datos reales", "admin@example.test")
                self.assertEqual(estado, "Enviada")
                self.assertEqual(respuesta, "250 queued as test-001")
            finally:
                server.shutdown()
                thread.join(timeout=5)
