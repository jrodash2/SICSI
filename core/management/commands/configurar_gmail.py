"""Configura el settings.py privado sin enviar mensajes ni publicar secretos."""
import ast
from getpass import getpass
import os
import re
import tempfile
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email

def actualizar_configuracion(source, correo, clave):
    valores = {
        'EMAIL_MODE': 'smtp',
        'EMAIL_BACKEND': 'core.email_backend.CustomEmailBackend',
        'EMAIL_HOST': 'smtp.gmail.com',
        'EMAIL_PORT': 587,
        'EMAIL_USE_TLS': True,
        'EMAIL_USE_SSL': False,
        'EMAIL_HOST_USER': correo,
        'EMAIL_HOST_PASSWORD': clave,
        'DEFAULT_FROM_EMAIL': correo,
    }
    tree = ast.parse(source)
    reemplazos = []
    vistos = set()
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            nombre = node.targets[0].id
            if nombre in valores:
                reemplazos.append((node.lineno - 1, node.end_lineno, f'{nombre} = {valores[nombre]!r}\n'))
                vistos.add(nombre)
    lineas = source.splitlines(keepends=True)
    for inicio, fin, texto in sorted(reemplazos, reverse=True):
        lineas[inicio:fin] = [texto]
    result = ''.join(lineas)
    for nombre, valor in valores.items():
        if nombre not in vistos:
            result += f'\n{nombre} = {valor!r}\n'
    ast.parse(result)
    return result

from core.management.actor_command import ComandoConUsuario

class Command(ComandoConUsuario):
    registrar_finalizacion = True
    help = 'Configura Gmail en config/settings.py privado. Solicita la clave oculta y no envía correos.'
    requires_system_checks = []
    def add_arguments(self, parser):
        parser.add_argument('--correo', help='Cuenta de Gmail o Google Workspace. La clave se solicita de forma oculta.')
    def handle(self, *args, **options):
        from pathlib import Path
        path = Path(settings.BASE_DIR) / 'config' / 'settings.py'
        correo = (options.get('correo') or input('Correo Gmail o Google Workspace: ')).strip()
        try:
            validate_email(correo)
        except ValidationError as exc:
            raise CommandError('El correo no tiene un formato válido.') from exc
        try:
            clave = ''.join(getpass('Contraseña de aplicación de Gmail (no se mostrará): ').split())
        except (EOFError, KeyboardInterrupt) as exc:
            raise CommandError('Configuración cancelada; no se modificó settings.py.') from exc
        if not re.fullmatch(r'[A-Za-z0-9]{16}', clave):
            raise CommandError('Use la contraseña de aplicación de 16 caracteres. No se modificó settings.py.')
        try:
            source = path.read_text(encoding='utf-8-sig')
            nuevo = actualizar_configuracion(source, correo, clave)
            descriptor, tempname = tempfile.mkstemp(prefix='.settings-', suffix='.tmp', dir=path.parent)
            try:
                with os.fdopen(descriptor, 'w', encoding='utf-8') as out:
                    out.write(nuevo)
                os.chmod(tempname, 0o600)
                os.replace(tempname, path)
            finally:
                if os.path.exists(tempname):
                    os.unlink(tempname)
        except (OSError, SyntaxError) as exc:
            raise CommandError('No se pudo actualizar el settings.py privado. Revise el archivo y sus permisos.') from exc
        self.stdout.write(self.style.SUCCESS('Gmail configurado en settings.py privado. No se imprimió la clave ni se enviaron correos. Reinicie SICSI y use Destinatarios → Probar correo.'))
