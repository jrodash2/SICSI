from pathlib import Path
import os
import tempfile
from unittest.mock import patch
from io import StringIO
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

class RespaldoTests(SimpleTestCase):
    def test_secreto_no_va_en_argumentos_y_temporal_se_elimina(self):
        password_file = None
        with tempfile.TemporaryDirectory() as root, override_settings(BACKUP_DIR=Path(root)):
            def ejecutar(comando, **kwargs):
                nonlocal password_file
                password_file = Path(kwargs['env']['PGPASSFILE'])
                self.assertTrue(password_file.exists())
                self.assertNotIn('PGPASSWORD', kwargs['env'])
                self.assertIn('--no-password', comando)
                if os.name != 'nt':
                    self.assertEqual(password_file.stat().st_mode & 0o777, 0o600)
                Path(comando[comando.index('--file') + 1]).write_bytes(b'PGDMP-test-only')
            with patch('core.management.commands.respaldar_bd.subprocess.run', side_effect=ejecutar):
                call_command('respaldar_bd', stdout=StringIO())
            self.assertEqual(len(list(Path(root).glob('*.dump'))), 1)
            self.assertFalse(list(Path(root).glob('*.parcial')))
        self.assertFalse(password_file.exists())
    def test_fallo_no_deja_archivo_que_parezca_respaldo_completo(self):
        with tempfile.TemporaryDirectory() as root, override_settings(BACKUP_DIR=Path(root)):
            with patch('core.management.commands.respaldar_bd.subprocess.run', side_effect=FileNotFoundError):
                with self.assertRaises(CommandError):
                    call_command('respaldar_bd')
            self.assertFalse(list(Path(root).iterdir()))
