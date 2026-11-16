from concurrent.futures import ThreadPoolExecutor
from datetime import date
from unittest.mock import patch
from django.db import connections, IntegrityError, transaction
from django.test import TestCase, TransactionTestCase
from core.models import Alerta, Servicio, Usuario
from core.services import enviar_alerta, procesar_alertas, renovar

class AlertasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Usuario.objects.create_superuser(username="admin", email="admin@example.test", password="test-password-only-2026")
        cls.s = Servicio.objects.create(codigo="PRUEBA", nombre="Licencia de prueba", periodicidad="anual", fecha_vencimiento=date(2026, 12, 31))
    @patch("core.services.entregar", return_value=("Enviada", "250 Aceptado para prueba"))
    def test_aviso_registra_respuesta_y_no_duplica(self, correo):
        self.assertEqual(enviar_alerta(self.s.pk, "45", date(2026, 11, 16)), "enviada")
        self.assertEqual(enviar_alerta(self.s.pk, "45", date(2026, 11, 16)), "omitida")
        self.assertEqual(correo.call_count, 1)
        alerta = Alerta.objects.get()
        self.assertEqual(alerta.destinatario, "admin@example.test")
        self.assertEqual(alerta.respuesta, "250 Aceptado para prueba")
        self.assertIsNotNone(alerta.enviada)
    @patch("core.services.entregar")
    def test_no_inventa_envios_retroactivos(self, correo):
        for tipo in ("45", "30", "15"):
            self.assertEqual(enviar_alerta(self.s.pk, tipo, date(2026, 12, 20)), "omitida")
        self.assertFalse(correo.called)
        self.assertFalse(Alerta.objects.exists())
    @patch("core.services.entregar", return_value=("Enviada", "250 OK"))
    def test_urgencia_inicial_unica_por_ciclo(self, correo):
        self.assertEqual(enviar_alerta(self.s.pk, "urgente", date(2026, 11, 16)), "omitida")
        self.assertEqual(enviar_alerta(self.s.pk, "urgente", date(2026, 11, 17)), "enviada")
        self.assertEqual(enviar_alerta(self.s.pk, "urgente", date(2026, 11, 18)), "omitida")
        self.assertEqual(correo.call_count, 1)
    @patch("core.services.entregar", side_effect=OSError("Conexión SMTP interrumpida"))
    def test_error_no_se_reintenta_automaticamente(self, correo):
        self.assertEqual(enviar_alerta(self.s.pk, "45", date(2026, 11, 16)), "fallida")
        self.assertEqual(enviar_alerta(self.s.pk, "45", date(2026, 11, 16)), "omitida")
        self.assertEqual(Alerta.objects.get().estado, Alerta.Estado.INCIERTA)
        self.assertEqual(correo.call_count, 1)
    @patch("core.services.entregar", return_value=("Enviada", "250 OK"))
    def test_renovacion_conserva_fechas_y_habilita_nuevo_ciclo(self, correo):
        enviar_alerta(self.s.pk, "45", date(2026, 11, 16))
        renovar(self.s.pk, {"nuevo_inicio": date(2027, 1, 1), "nuevo_vencimiento": date(2027, 12, 31), "observaciones": "Confirmación de prueba"})
        self.s.refresh_from_db()
        self.assertEqual(self.s.ciclo, 2)
        self.assertEqual(self.s.renovaciones.get().vencimiento_anterior, date(2026, 12, 31))
        self.assertEqual(self.s.gestiones.get().tramite, "Renovado")
        self.assertEqual(enviar_alerta(self.s.pk, "45", date(2027, 11, 16)), "enviada")
        self.assertEqual(correo.call_count, 2)
    @patch("core.services.entregar", return_value=("Enviada", "250 OK"))
    def test_cron_ejecuta_los_tres_umbrales_y_excluye_permanentes(self, correo):
        Servicio.objects.create(codigo="D30", nombre="Servicio 30", fecha_vencimiento=date(2026, 12, 16))
        Servicio.objects.create(codigo="D15", nombre="Servicio 15", fecha_vencimiento=date(2026, 12, 1))
        Servicio.objects.create(codigo="PER", nombre="Permanente", periodicidad="permanente", fecha_vencimiento=date(2026, 12, 31))
        result = procesar_alertas(date(2026, 11, 16))
        self.assertEqual(result["enviada"], 3)
        self.assertEqual(correo.call_count, 3)
        self.assertEqual(procesar_alertas(date(2026, 11, 17))["enviada"], 0)
    def test_base_rechaza_clave_duplicada(self):
        Alerta.objects.create(servicio=self.s, ciclo=1, tipo="45", destinatario="admin@example.test")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Alerta.objects.create(servicio=self.s, ciclo=1, tipo="45", destinatario="admin@example.test")

class ConcurrenciaPostgreSQLTests(TransactionTestCase):
    def test_dos_ejecuciones_solo_envian_una_vez(self):
        Usuario.objects.create_superuser(username="admin", email="admin@example.test", password="test-password-only-2026")
        s = Servicio.objects.create(codigo="PARALELO", nombre="Prueba de concurrencia", fecha_vencimiento=date(2026, 12, 31))
        def ejecutar():
            connections.close_all()
            try:
                return enviar_alerta(s.pk, "45", date(2026, 11, 16))
            finally:
                connections.close_all()
        with patch("core.services.entregar", return_value=("Enviada", "250 OK")) as correo:
            with ThreadPoolExecutor(max_workers=2) as executor:
                resultados = list(executor.map(lambda _: ejecutar(), range(2)))
        self.assertCountEqual(resultados, ["enviada", "omitida"])
        self.assertEqual(correo.call_count, 1)
        self.assertEqual(Alerta.objects.count(), 1)
