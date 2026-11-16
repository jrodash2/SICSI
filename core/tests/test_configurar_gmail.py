import ast
from io import StringIO
from pathlib import Path
import tempfile
from unittest.mock import patch
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from core.management.commands.configurar_gmail import actualizar_configuracion

SOURCE = '''SECRET_KEY = "clave-privada-de-prueba"
DATABASES = {"default": {"NAME": "sicsi", "PASSWORD": "clave-db-ficticia"}}
EMAIL_MODE = "console"
EMAIL_BACKEND = "anterior.backend"
EMAIL_HOST_PASSWORD = ""
PRIVATE_MEDIA_ROOT = "carpeta-privada"
'''

class ConfigurarGmailTests(TestCase):
    def test_preserva_base_secret_key_y_ruta_privada(self):
        result = actualizar_configuracion(SOURCE, 'cuenta@example.test', 'abcdefghijklmnop')
        tree = ast.parse(result)
        variables = {n.targets[0].id: ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)}
        self.assertEqual(variables['DATABASES']['default']['PASSWORD'], 'clave-db-ficticia')
        self.assertEqual(variables['SECRET_KEY'], 'clave-privada-de-prueba')
        self.assertEqual(variables['PRIVATE_MEDIA_ROOT'], 'carpeta-privada')
        self.assertEqual(variables['EMAIL_BACKEND'], 'core.email_backend.CustomEmailBackend')
        self.assertEqual(variables['EMAIL_MODE'], 'smtp')
        self.assertEqual(variables['EMAIL_PORT'], 587)
        self.assertTrue(variables['EMAIL_USE_TLS'])
        self.assertFalse(variables['EMAIL_USE_SSL'])
    def test_comando_guarda_clave_sin_espacios_sin_imprimir_ni_enviar(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'config' / 'settings.py'
            path.parent.mkdir()
            path.write_text(SOURCE)
            output = StringIO()
            with override_settings(BASE_DIR=Path(root)), patch('core.management.commands.configurar_gmail.getpass', return_value='abcd efgh ijkl mnop'), patch('core.mail.entregar') as smtp:
                call_command('configurar_gmail', correo='cuenta@example.test', stdout=output)
            self.assertIn("EMAIL_HOST_PASSWORD = 'abcdefghijklmnop'", path.read_text())
            self.assertNotIn('abcdefghijklmnop', output.getvalue())
            self.assertFalse(smtp.called)
            self.assertFalse(list(path.parent.glob('.settings-*.tmp')))
    def test_clave_invalida_no_cambia_archivo(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'config' / 'settings.py'
            path.parent.mkdir()
            path.write_text(SOURCE)
            with override_settings(BASE_DIR=Path(root)), patch('core.management.commands.configurar_gmail.getpass', return_value='incompleta'):
                with self.assertRaises(CommandError):
                    call_command('configurar_gmail', correo='cuenta@example.test')
            self.assertEqual(path.read_text(), SOURCE)
