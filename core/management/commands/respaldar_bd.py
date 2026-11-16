import os
from pathlib import Path
import subprocess
import tempfile
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.management.actor_command import ComandoConUsuario

class Command(ComandoConUsuario):
    registrar_finalizacion = True
    help = "Crea un respaldo PostgreSQL privado con pg_dump (requiere el cliente instalado)."
    def handle(self, *args, **options):
        db = settings.DATABASES["default"]
        directorio = Path(settings.BACKUP_DIR)
        directorio.mkdir(mode=0o700, parents=True, exist_ok=True)
        destino = directorio / f"sicsi-{timezone.now().strftime('%Y%m%dT%H%M%S%fZ')}.dump"
        parcial = destino.with_suffix(".parcial")
        def escapar(valor):
            texto = str(valor)
            if "\n" in texto or "\r" in texto:
                raise CommandError("La configuración de conexión no puede contener saltos de línea.")
            return texto.replace("\\", "\\\\").replace(":", "\\:")
        with tempfile.TemporaryDirectory(prefix="sicsi-pg-") as temporal:
            passfile = Path(temporal) / "pgpass.conf"
            contenido = ":".join(escapar(db.get(k, "")) for k in ["HOST", "PORT", "NAME", "USER", "PASSWORD"])
            passfile.write_text(contenido + "\n", encoding="utf-8")
            passfile.chmod(0o600)
            entorno = os.environ.copy()
            entorno.pop("PGPASSWORD", None)
            entorno["PGPASSFILE"] = str(passfile)
            entorno["PGSSLMODE"] = db.get("OPTIONS", {}).get("sslmode", "prefer")
            comando = [settings.PG_DUMP_BIN, "--host", db["HOST"], "--port", str(db["PORT"]), "--username", db["USER"], "--dbname", db["NAME"], "--format=custom", "--no-owner", "--no-acl", "--file", str(parcial), "--no-password"]
            try:
                # El archivo existe con permisos privados antes de que pg_dump escriba.
                descriptor = os.open(parcial, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.close(descriptor)
                subprocess.run(comando, env=entorno, check=True, capture_output=True, timeout=3600)
                parcial.replace(destino)
            except (OSError, subprocess.SubprocessError) as exc:
                parcial.unlink(missing_ok=True)
                raise CommandError("Falló pg_dump. Revise PG_DUMP_BIN, versión del cliente, acceso a PostgreSQL y permisos; no se imprimen credenciales.") from exc
        self.stdout.write(self.style.SUCCESS(f"Respaldo privado: {destino}"))
