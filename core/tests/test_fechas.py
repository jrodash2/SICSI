from datetime import date, datetime, timezone as utc
from unittest.mock import patch
from django.test import SimpleTestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from core.forms import RenovacionForm
from core.models import Servicio

class CalendarioTests(SimpleTestCase):
    def servicio(self, **kwargs):
        return Servicio(codigo="PRUEBA", nombre="Prueba", fecha_vencimiento=date(2026, 12, 31), periodicidad="anual", **kwargs)
    def test_umbrales_exactos_sin_redondeo(self):
        s = self.servicio()
        for dia, esperado in [(date(2026, 11, 16), 45), (date(2026, 12, 1), 30), (date(2026, 12, 16), 15), (date(2026, 12, 31), 0), (date(2027, 1, 1), -1)]:
            with self.subTest(dia=dia):
                self.assertEqual(s.dias_al_vencimiento(dia), esperado)
    def test_exclusiones(self):
        for cambio in [{"periodicidad": "permanente"}, {"fecha_vencimiento": None}, {"requiere_validacion": True}, {"estado": "Cancelado"}]:
            s = self.servicio()
            for k, v in cambio.items():
                setattr(s, k, v)
            self.assertIsNone(s.dias_al_vencimiento(date(2026, 11, 16)))
    def test_calendario_guatemala_aunque_utc_ya_cambio(self):
        with patch("django.utils.timezone.now", return_value=datetime(2026, 11, 17, 3, tzinfo=utc.utc)):
            self.assertEqual(timezone.localdate(), date(2026, 11, 16))
            self.assertEqual(self.servicio().dias, 45)
    def test_bisiesto(self):
        s = Servicio(fecha_vencimiento=date(2024, 3, 15), periodicidad="anual")
        self.assertEqual(s.dias_al_vencimiento(date(2024, 1, 30)), 45)
    def test_contradiccion_requiere_marca_y_motivo(self):
        s = self.servicio(fecha_inicio=date(2027, 1, 1))
        with self.assertRaises(ValidationError):
            s.clean()
        s.requiere_validacion = True
        with self.assertRaises(ValidationError):
            s.clean()
        s.motivo_validacion = "Dos fechas incompatibles en la fuente"
        s.clean()
    def test_renovacion_valida_orden_de_fechas(self):
        self.assertFalse(RenovacionForm({"nuevo_inicio": "2027-02-01", "nuevo_vencimiento": "2027-01-01"}).is_valid())
        self.assertFalse(RenovacionForm({"nuevo_vencimiento": "2026-02-30"}).is_valid())
