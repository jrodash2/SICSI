import csv
from io import StringIO
from pathlib import Path
import tempfile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from core.models import Servicio

class ImportacionTests(TestCase):
    def archivo(self, root, filas, campos=None):
        path = Path(root) / "servicios.csv"
        campos = campos or ["codigo", "nombre", "fecha_inicio", "fecha_vencimiento", "motivo_validacion"]
        with path.open("w", encoding="utf-8", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=campos)
            writer.writeheader()
            writer.writerows(filas)
        return str(path)
    def test_simulacion_y_aplicacion_marcan_contradicciones(self):
        with tempfile.TemporaryDirectory() as root:
            archivo = self.archivo(root, [{"codigo": "IMP", "nombre": "Servicio de prueba", "fecha_inicio": "2027-01-01", "fecha_vencimiento": "2026-01-01"}])
            call_command("importar_servicios", archivo, stdout=StringIO())
            self.assertFalse(Servicio.objects.exists())
            call_command("importar_servicios", archivo, aplicar=True, stdout=StringIO())
            self.assertTrue(Servicio.objects.get().requiere_validacion)
            self.assertIsNone(Servicio.objects.get().dias)
    def test_rechaza_columnas_no_admitidas_y_numero_inicial(self):
        with tempfile.TemporaryDirectory() as root:
            archivo = self.archivo(root, [{"codigo": "X", "nombre": "Prueba", "password": "NO-IMPORTAR"}], ["codigo", "nombre", "password"])
            with self.assertRaises(CommandError):
                call_command("importar_servicios", archivo, aplicar=True)
            archivo = self.archivo(root, [{"codigo": "X", "nombre": "Prueba"}])
            with self.assertRaises(CommandError):
                call_command("importar_servicios", archivo, inicial_12=True)
            self.assertFalse(Servicio.objects.exists())
    def test_error_en_segunda_fila_no_importa_primera(self):
        with tempfile.TemporaryDirectory() as root:
            archivo = self.archivo(root, [{"codigo": "A", "nombre": "Válido"}, {"codigo": "B", "nombre": "Inválido", "fecha_vencimiento": "2026-02-30"}])
            with self.assertRaises(CommandError):
                call_command("importar_servicios", archivo, aplicar=True)
            self.assertFalse(Servicio.objects.exists())
