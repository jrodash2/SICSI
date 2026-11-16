from contextlib import contextmanager
from contextvars import ContextVar

_usuario = ContextVar("sicsi_usuario", default=None)
_origen = ContextVar("sicsi_origen", default="sistema")

def usuario_actual():
    usuario = _usuario.get()
    return usuario if usuario is not None and usuario.is_authenticated else None

def origen_actual():
    return _origen.get()

def nombre_usuario(usuario):
    if usuario is None:
        return ""
    completo = usuario.get_full_name().strip()
    return (f"{usuario.username} · {completo}" if completo else usuario.username)[:320]

def etiqueta_autor(nombre, origen):
    return nombre or {"historico": "Autor no registrado · registro anterior", "consola": "Consola · sin usuario indicado", "sistema": "Sistema · tarea automática", "web": "Acceso no autenticado"}.get(origen, "Autor no registrado")

@contextmanager
def contexto_usuario(usuario=None, origen="sistema"):
    token_u = _usuario.set(usuario)
    token_o = _origen.set(origen)
    try:
        yield
    finally:
        _usuario.reset(token_u)
        _origen.reset(token_o)
