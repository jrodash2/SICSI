"""Cifrado del documento y sus accesos. La clave queda fuera de la BD y de Git."""
import json
import os
from pathlib import Path
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

def ruta_clave():
    return Path(getattr(settings, "ACTA_KEY_FILE", Path(settings.PRIVATE_MEDIA_ROOT) / ".acta.key"))

def cifrador(crear=False):
    path = ruta_clave()
    if crear:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, "wb") as output:
                output.write(Fernet.generate_key())
    try:
        return Fernet(path.read_bytes().strip())
    except (OSError, ValueError) as exc:
        raise ImproperlyConfigured("Falta la clave privada del acta o no es válida. Restaure private_media/.acta.key del respaldo; no la publique ni la sustituya.") from exc

def cifrar_bytes(data):
    return cifrador(crear=True).encrypt(data)

def descifrar_bytes(data):
    try:
        return cifrador().decrypt(bytes(data))
    except InvalidToken as exc:
        raise ImproperlyConfigured("La clave privada del acta no corresponde a este respaldo.") from exc

def cifrar_json(data):
    return cifrar_bytes(json.dumps(data, ensure_ascii=False).encode("utf-8"))

def descifrar_json(data):
    return json.loads(descifrar_bytes(data).decode("utf-8"))
