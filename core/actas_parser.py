"""Lee DOCX como datos. No ejecuta macros, enlaces ni instrucciones de su contenido."""
from datetime import date
from hashlib import sha256
from io import BytesIO
import re
import unicodedata
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

N = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
MONTHS = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12}

def normalizar(value):
    value = unicodedata.normalize("NFKD", value)
    return "".join(c for c in value.lower() if c.isalnum() and not unicodedata.combining(c))

def texto_parrafo(p):
    textos = []
    for item in p.iter():
        tag = item.tag.rsplit("}", 1)[-1]
        if tag == "t":
            textos.append(item.text or "")
        elif tag == "tab":
            textos.append("\t")
        elif tag in {"br", "cr"}:
            textos.append("\n")
    return "".join(textos)

def xml_seguro(data):
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise ValueError("XML con declaraciones no admitidas.")
    return ET.fromstring(data)

def formato_tabla(valores):
    formatos = set()
    for value in valores:
        match = re.fullmatch(r"\s*(\d{1,2})/(\d{1,2})/(\d{4})\s*", value)
        if match:
            a, b, _ = map(int, match.groups())
            if a > 12 >= b:
                formatos.add("DMY")
            if b > 12 >= a:
                formatos.add("MDY")
    return next(iter(formatos)) if len(formatos) == 1 else None

def interpretar_fecha(value, formato=None):
    value = value.strip()
    if not value or value.upper() in {"PERMANENTE", "PAGO MENSUAL", "INSUMO", "(PENDIENTE DE FECHA)", "(SIN ESPECIFICAR)"}:
        return None, ""
    match = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", value)
    if not match:
        return None, "La fuente no especifica una fecha completa válida; se conserva el texto original."
    a, b, year = map(int, match.groups())
    if a > 12 and b <= 12:
        day, month = a, b
    elif b > 12 and a <= 12:
        day, month = b, a
    elif a == b:
        day, month = a, b
    elif formato == "MDY":
        month, day = a, b
    elif formato == "DMY":
        day, month = a, b
    else:
        return None, "Fecha ambigua entre día/mes y mes/día; requiere confirmación."
    try:
        parsed = date(year, month, day)
    except ValueError:
        return None, "Fecha imposible en el calendario; se conserva el texto original."
    if a != b and a <= 12 and b <= 12:
        return parsed, f"Fecha ambigua {value}; interpretada como {parsed.isoformat()} por el patrón {formato} de su tabla. Confirmar antes de activar alertas."
    return parsed, ""

def leer_acta(data):
    if len(data) > 15 * 1024 * 1024:
        raise ValueError("El DOCX supera 15 MB.")
    try:
        with ZipFile(BytesIO(data)) as archive:
            if len(archive.infolist()) > 5000 or sum(i.file_size for i in archive.infolist()) > 80 * 1024 * 1024:
                raise ValueError("El DOCX excede los límites de lectura.")
            root = xml_seguro(archive.read("word/document.xml"))
            body = root.find("w:body", N)
            if body is None:
                raise ValueError("El DOCX no contiene un cuerpo de documento.")
            blocks = []
            tables = []
            for node in body:
                if node.tag == f"{{{N['w']}}}p":
                    text = texto_parrafo(node)
                    if text.strip():
                        blocks.append({"tipo": "parrafo", "texto": text})
                elif node.tag == f"{{{N['w']}}}tbl":
                    rows = [["\n".join(texto_parrafo(p) for p in cell.findall("w:p", N)) for cell in row.findall("w:tc", N)] for row in node.findall("w:tr", N)]
                    table = {"tipo": "tabla", "filas": rows}
                    blocks.append(table)
                    tables.append(table)
            extras = []
            for name in archive.namelist():
                if name.startswith("word/") and name.endswith(".xml") and ("header" in name or "footer" in name or name in {"word/footnotes.xml", "word/endnotes.xml", "word/comments.xml"}):
                    part = xml_seguro(archive.read(name))
                    texts = [texto_parrafo(p) for p in part.findall(".//w:p", N)]
                    if any(t.strip() for t in texts):
                        extras.append({"parte": name, "parrafos": texts})
            imagenes = len([n for n in archive.namelist() if n.startswith("word/media/")])
    except (BadZipFile, KeyError, ET.ParseError) as exc:
        raise ValueError("El archivo no es un DOCX legible o está incompleto.") from exc
    tipos = {}
    for table in tables:
        headers = [normalizar(c) for c in table["filas"][0]] if table["filas"] else []
        if {"servicio", "cantidad", "vencimiento", "empresa", "contacto", "telefono"}.issubset(headers):
            kind = "servicios"
        elif headers and headers[0] == "nombre" and any("justificacion" in h for h in headers):
            kind = "catalogo"
        elif headers and "plataforma" in headers[0] and any("usuario" in h for h in headers):
            kind = "accesos"
        else:
            continue  # Se conserva completa en blocks aunque no sea una tabla reconocida.
        if kind in tipos:
            raise ValueError("Hay más de una tabla del mismo tipo; revise el documento antes de importar.")
        tipos[kind] = table
    if "servicios" not in tipos:
        raise ValueError("No se encontró una tabla de servicios con cantidad, vencimiento, empresa y contacto.")
    servicios = tipos["servicios"]["filas"][1:]
    catalogo = tipos.get("catalogo", {}).get("filas", [])[1:]
    accesos = tipos.get("accesos", {}).get("filas", [])[1:]
    formato_servicios = formato_tabla([row[3] for row in servicios if len(row) >= 4])
    formato_catalogo = formato_tabla([row[2] for row in catalogo if len(row) >= 3])
    preparados = []
    for index, row in enumerate(servicios, start=1):
        if len(row) != 7:
            raise ValueError(f"La fila {index} de servicios no contiene siete columnas.")
        numero, nombre, cantidad, rawdate, empresa, contacto, telefono = [v.strip() for v in row]
        fecha, motivo = interpretar_fecha(rawdate, formato_servicios)
        coincidencias = [r for r in catalogo if len(r) >= 3 and normalizar(r[0]) == normalizar(nombre)]
        for referencia in coincidencias:
            other, _ = interpretar_fecha(referencia[2], formato_catalogo)
            if fecha and other and fecha != other:
                motivo = (motivo + " " if motivo else "") + f"Contradicción con catálogo: {referencia[2].strip()}; tabla de servicios: {rawdate}. Conservar ambas y validar."
        preparados.append({"numero": numero or str(index), "nombre": nombre, "capacidad": cantidad, "fecha_texto": rawdate, "fecha_vencimiento": fecha.isoformat() if fecha else None, "proveedor": empresa, "contacto_nombre": "" if contacto.lower().startswith("(sin ") else contacto, "contacto_telefono": "" if telefono.lower().startswith("(sin ") else telefono, "periodicidad": "permanente" if rawdate.upper() == "PERMANENTE" else "mensual" if rawdate.upper() == "PAGO MENSUAL" else "por definir", "requiere_validacion": bool(motivo), "motivo_validacion": motivo})
    fecha_documento = None
    for block in blocks:
        if block["tipo"] != "parrafo":
            continue
        match = re.search(r"\b(\d{1,2}) de (\w+) de (\d{4})\b", block["texto"], re.I)
        if match and match[2].lower() in MONTHS:
            try:
                fecha_documento = date(int(match[3]), MONTHS[match[2].lower()], int(match[1])).isoformat()
            except ValueError:
                pass
            break
    return {"sha256": sha256(data).hexdigest(), "fecha_documento": fecha_documento, "bloques": blocks, "extras": extras, "servicios": preparados, "catalogo": catalogo, "accesos": accesos, "formato_servicios": formato_servicios, "formato_catalogo": formato_catalogo, "resumen": {"servicios": len(preparados), "catalogo": len(catalogo), "accesos": len(accesos), "parrafos": sum(b['tipo'] == 'parrafo' for b in blocks), "tablas": len(tables), "imagenes": imagenes, "servicios_por_validar": sum(s['requiere_validacion'] for s in preparados)}}
