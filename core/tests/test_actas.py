from datetime import date
from io import BytesIO, StringIO
from pathlib import Path
import tempfile
from zipfile import ZipFile
from xml.etree import ElementTree as ET
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from core.actas_crypto import descifrar_bytes, descifrar_json, ruta_clave
from core.actas_parser import interpretar_fecha, leer_acta
from core.models import ActaEntrega, Auditoria, ElementoActa, Servicio, Usuario

NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'

def docx_prueba(catalogo_malo=False):
    document = ET.Element(f'{{{NS}}}document')
    body = ET.SubElement(document, f'{{{NS}}}body')
    def p(parent, text):
        node = ET.SubElement(parent, f'{{{NS}}}p')
        run = ET.SubElement(node, f'{{{NS}}}r')
        ET.SubElement(run, f'{{{NS}}}t').text = text
    def tabla(rows):
        table = ET.SubElement(body, f'{{{NS}}}tbl')
        for row in rows:
            tr = ET.SubElement(table, f'{{{NS}}}tr')
            for cell in row:
                tc = ET.SubElement(tr, f'{{{NS}}}tc')
                p(tc, cell)
    p(body, 'Guatemala 11 de noviembre de 2026.')
    p(body, 'Identidad ficticia: TEST-000. Contenido que no debe perderse.')
    p(body, 'Contraseña de prueba: secreto-sintetico-no-real')
    tabla([['Plataforma / Servicio', 'Usuario / Referencia', 'Contraseña / Notas'], ['Plataforma ficticia', 'usuario@example.test', 'secreto-sintetico-no-real']])
    rows = [['Nombre', 'Justificación / Descripción', 'Vencimiento / Tipo'], ['ASISTENCIA', 'Descripción literal', '7/12/2026'], ['LICENCIA', 'Segunda fila', '30/11/2026'], ['LICENCIA', 'Fila repetida original', '30/11/2026']]
    if catalogo_malo:
        rows.append(['Fila incompleta', 'Solo dos columnas'])
    tabla(rows)
    tabla([['No.', 'Servicio', 'Cantidad', 'Vencimiento', 'Empresa', 'Contacto', 'Teléfono'], ['1', 'INTERNET PRUEBA', '150 MB', '11/30/2026', 'Proveedor ficticio', 'Contacto ficticio', '00000000'], ['2', 'ASISTENCIA', '1', '12/12/2026', '', '', ''], ['3', 'AMBIGUO', '1', '3/4/2027', '', '', '']])
    output = BytesIO()
    with ZipFile(output, 'w') as archive:
        archive.writestr('word/document.xml', ET.tostring(document, encoding='utf-8', xml_declaration=True))
        archive.writestr('word/media/test.bin', b'imagen-sintetica-conservada')
    return output.getvalue()

class ParserActasTests(SimpleTestCase):
    def test_formatos_distintos_contradiccion_y_duplicados(self):
        parsed = leer_acta(docx_prueba())
        self.assertEqual(parsed['formato_servicios'], 'MDY')
        self.assertEqual(parsed['formato_catalogo'], 'DMY')
        self.assertEqual(parsed['servicios'][0]['fecha_vencimiento'], '2026-11-30')
        self.assertTrue(parsed['servicios'][1]['requiere_validacion'])
        self.assertIn('Contradicción', parsed['servicios'][1]['motivo_validacion'])
        self.assertTrue(parsed['servicios'][2]['requiere_validacion'])
        self.assertEqual(len(parsed['catalogo']), 3)
        self.assertEqual(parsed['resumen']['imagenes'], 1)
        self.assertIn('secreto-sintetico-no-real', str(parsed['bloques']))
    def test_no_inventa_fecha_de_un_mes_o_fecha_imposible(self):
        self.assertEqual(interpretar_fecha('ENERO')[0], None)
        self.assertIsNone(interpretar_fecha('31/02/2027', 'DMY')[0])
        self.assertIsNone(interpretar_fecha('PAGO MENSUAL')[0])
        self.assertIsNone(interpretar_fecha('PERMANENTE')[0])
    def test_rechaza_archivo_que_no_es_docx(self):
        with self.assertRaises(ValueError):
            leer_acta(b'no es zip')

class ImportarActaTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = override_settings(PRIVATE_MEDIA_ROOT=self.root / 'privado')
        self.config.enable()
        self.addCleanup(self.config.disable)
        self.archivo = self.root / 'acta.docx'
        self.original = docx_prueba()
        self.archivo.write_bytes(self.original)
    def importar(self):
        call_command('importar_acta', str(self.archivo), aplicar=True, stdout=StringIO())
        return ActaEntrega.objects.get()
    def test_solo_revision_no_escribe_datos_ni_clave(self):
        call_command('importar_acta', str(self.archivo), stdout=StringIO())
        self.assertFalse(Servicio.objects.exists())
        self.assertFalse(ActaEntrega.objects.exists())
        self.assertFalse(ruta_clave().exists())
    def test_carga_completa_cifrada_y_original_byte_por_byte(self):
        acta = self.importar()
        self.assertEqual(Servicio.objects.count(), 3)
        self.assertEqual(ElementoActa.objects.filter(tipo='catalogo').count(), 3)
        self.assertEqual(ElementoActa.objects.filter(tipo='acceso').count(), 1)
        self.assertEqual(descifrar_bytes(acta.archivo_cifrado), self.original)
        self.assertEqual(acta.fecha_documento, date(2026, 11, 11))
        self.assertNotIn(b'secreto-sintetico-no-real', bytes(acta.contenido_cifrado))
        self.assertNotIn(b'secreto-sintetico-no-real', bytes(acta.elementos.get(tipo='acceso').contenido_cifrado))
        self.assertIn('secreto-sintetico-no-real', str(descifrar_json(acta.contenido_cifrado)))
        self.assertNotIn('secreto-sintetico-no-real', str(list(Auditoria.objects.values())))
    def test_reimportar_mismos_bytes_no_duplica_ni_sobrescribe(self):
        self.importar()
        s = Servicio.objects.first()
        s.nombre = 'Edición local conservada'
        s.save()
        call_command('importar_acta', str(self.archivo), aplicar=True, stdout=StringIO())
        self.assertEqual(ActaEntrega.objects.count(), 1)
        self.assertEqual(Servicio.objects.count(), 3)
        s.refresh_from_db()
        self.assertEqual(s.nombre, 'Edición local conservada')
    def test_fila_invalida_revierte_toda_la_importacion(self):
        self.archivo.write_bytes(docx_prueba(catalogo_malo=True))
        with self.assertRaises(CommandError):
            self.importar()
        self.assertFalse(ActaEntrega.objects.exists())
        self.assertFalse(Servicio.objects.exists())
        self.assertFalse(ElementoActa.objects.exists())
    def test_perder_clave_no_genera_sustituto_ni_expone_cifrado(self):
        acta = self.importar()
        ruta_clave().unlink()
        with self.assertRaises(ImproperlyConfigured):
            descifrar_bytes(acta.archivo_cifrado)
        self.assertFalse(ruta_clave().exists())
    def test_vistas_privadas_documento_completo_y_auditoria(self):
        acta = self.importar()
        url = reverse('acta_detalle', args=[acta.pk])
        self.assertEqual(Client().get(url).status_code, 302)
        self.assertEqual(Client().get(reverse('acta_descargar', args=[acta.pk])).status_code, 302)
        user = Usuario.objects.create_superuser(username='admin', email='admin@example.test', password='test-password-only-2026')
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse('actas')).status_code, 200)
        response = self.client.get(url)
        self.assertContains(response, 'secreto-sintetico-no-real')
        self.assertContains(response, 'Identidad ficticia')
        self.assertEqual(response['Cache-Control'], 'no-store, private')
        download = self.client.get(reverse('acta_descargar', args=[acta.pk]))
        self.assertEqual(b''.join(download.streaming_content), self.original)
        self.assertTrue(Auditoria.objects.filter(accion='DESCARGAR_ACTA').exists())
        ruta_clave().unlink()
        self.assertEqual(self.client.get(url).status_code, 503)
