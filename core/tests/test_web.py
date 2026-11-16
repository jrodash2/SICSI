from datetime import date
from io import BytesIO
from pathlib import Path
import tempfile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from openpyxl import load_workbook
from core.models import Alerta, Auditoria, Documento, Gestion, Servicio, Usuario
from core.services import registrar_gestion

class WebTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = Usuario.objects.create_superuser(username="admin", email="admin@example.test", password="test-password-only-2026")
        cls.servicio = Servicio.objects.create(codigo="WEB", nombre="Servicio <script>alert(1)</script>", periodicidad="anual", fecha_vencimiento=date(2026, 12, 31))
    def setUp(self):
        self.client.force_login(self.user)
    def test_todas_las_pantallas_renderizan(self):
        for name in ["dashboard", "servicios", "servicio_crear", "gestiones", "alertas", "reportes", "auditoria", "password_change"]:
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        for name in ["servicio_detalle", "servicio_editar", "servicio_eliminar", "servicio_renovar", "gestion_crear", "documento_crear"]:
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name, args=[self.servicio.pk])).status_code, 200)
    def test_xss_se_escapa_en_detalle(self):
        response = self.client.get(reverse("servicio_detalle", args=[self.servicio.pk]))
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")
        self.assertNotContains(response, "<script>alert(1)</script>")
    def test_no_hay_registro_publico_y_las_cuentas_nuevas_no_son_administradoras(self):
        anon = Client()
        self.assertEqual(anon.get(reverse("servicios")).status_code, 302)
        self.assertEqual(anon.get("/registro/").status_code, 404)
        self.assertEqual(anon.get("/admin/").status_code, 404)
        usuario = Usuario.objects.create_user(username="consulta_nueva", email="consulta-nueva@example.test", password="test-password-only-2026")
        self.assertFalse(usuario.is_superuser)
        self.assertFalse(usuario.puede_editar)
    def test_csrf_obligatorio_y_logout_solo_post(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(reverse("servicio_crear"), {}).status_code, 403)
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
    def datos(self):
        return {"codigo": "WEB", "nombre": "Actualizado", "periodicidad": "anual", "estado": "Activo", "tramite": "Pendiente", "fecha_vencimiento": "2026-12-31", "version": self.servicio.version}
    def test_edicion_registra_historial_de_estado_y_auditoria(self):
        data = self.datos()
        data["tramite"] = "Trasladado a Compras"
        response = self.client.post(reverse("servicio_editar", args=[self.servicio.pk]), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Gestion.objects.get().tramite, data["tramite"])
        self.assertTrue(Auditoria.objects.filter(accion="EDITAR").exists())
    def test_formulario_desactualizado_no_sobrescribe(self):
        data = self.datos()
        registrar_gestion(self.servicio.pk, {"fecha": date(2026, 11, 16), "tipo": "Prueba", "descripcion": "Cambio concurrente", "tramite": "En trámite"})
        response = self.client.post(reverse("servicio_editar", args=[self.servicio.pk]), data)
        self.assertContains(response, "Recargue antes de editar")
        self.servicio.refresh_from_db()
        self.assertEqual(self.servicio.tramite, "En trámite")
    def test_fecha_con_alertas_solo_cambia_con_renovacion(self):
        Alerta.objects.create(servicio=self.servicio, ciclo=1, tipo="45", destinatario="admin@example.test")
        data = self.datos()
        data["fecha_vencimiento"] = "2027-12-31"
        response = self.client.post(reverse("servicio_editar", args=[self.servicio.pk]), data)
        self.assertContains(response, "Use Confirmar renovación")
        self.servicio.refresh_from_db()
        self.assertEqual(self.servicio.fecha_vencimiento, date(2026, 12, 31))
    def test_borrado_con_historial_se_bloquea(self):
        registrar_gestion(self.servicio.pk, {"fecha": date(2026, 11, 16), "tipo": "Prueba", "descripcion": "Historial", "tramite": "En trámite"})
        self.client.post(reverse("servicio_eliminar", args=[self.servicio.pk]))
        self.assertTrue(Servicio.objects.filter(pk=self.servicio.pk).exists())
        self.assertFalse(Auditoria.objects.filter(accion="ELIMINAR").exists())
    def test_gestiones_muestra_ultima_del_tramite_abierto(self):
        for estado in ["Pendiente", "En trámite"]:
            registrar_gestion(self.servicio.pk, {"fecha": date(2026, 11, 16), "tipo": estado, "descripcion": "Prueba", "tramite": estado})
        response = self.client.get(reverse("gestiones"))
        self.assertEqual(response.context["pagina"].paginator.count, 1)
        registrar_gestion(self.servicio.pk, {"fecha": date(2026, 11, 16), "tipo": "Cerrar", "descripcion": "Prueba", "tramite": "Renovado"})
        self.assertEqual(self.client.get(reverse("gestiones")).context["pagina"].paginator.count, 0)
        self.assertEqual(Gestion.objects.count(), 3)
    def test_archivos_privados_y_rechazo_de_pdf_falso(self):
        with tempfile.TemporaryDirectory() as root, override_settings(MEDIA_ROOT=root):
            url = reverse("documento_crear", args=[self.servicio.pk])
            false = SimpleUploadedFile("falso.pdf", b"NO ES PDF", content_type="application/pdf")
            self.assertContains(self.client.post(url, {"archivo": false}), "estructura PDF")
            self.assertFalse(Documento.objects.exists())
            file = SimpleUploadedFile("respaldo.pdf", b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF", content_type="application/pdf")
            self.assertEqual(self.client.post(url, {"archivo": file}).status_code, 302)
            doc = Documento.objects.get()
            self.assertNotIn("respaldo.pdf", doc.archivo.name)
            download = self.client.get(reverse("documento_descargar", args=[doc.pk]))
            self.assertEqual(download.status_code, 200)
            self.assertIn(b"%PDF-", b"".join(download.streaming_content))
            self.assertEqual(Client().get(reverse("documento_descargar", args=[doc.pk])).status_code, 302)
            self.assertEqual(self.client.get("/documentos-no-publicos/" + doc.archivo.name).status_code, 404)
    def test_reportes_y_formula_excel_no_ejecutable(self):
        self.servicio.nombre = '=HYPERLINK("https://example.test")'
        self.servicio.save()
        response = self.client.get(reverse("exportar", args=["xlsx"]))
        self.assertEqual(response.status_code, 200)
        book = load_workbook(BytesIO(response.content))
        self.assertEqual(book.active["B2"].data_type, "s")
        pdf = self.client.get(reverse("exportar", args=["pdf"]))
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.content.startswith(b"%PDF-"))
        self.assertEqual(self.client.get(reverse("exportar", args=["pdf"]), {"desde": "no-es-fecha"}).status_code, 400)
    def test_contrasena_invalida_otras_sesiones_sin_auditar_claves(self):
        otro = Client()
        otro.force_login(self.user)
        newpass = "otra-test-password-larga-2026"
        response = self.client.post(reverse("password_change"), {"old_password": "test-password-only-2026", "new_password1": newpass, "new_password2": newpass})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(otro.get(reverse("dashboard")).status_code, 302)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)
        self.assertNotIn(newpass, str(list(Auditoria.objects.values())))

class ControlAccesoTests(TestCase):
    def setUp(self):
        Usuario.objects.create_superuser(username="admin", email="admin@example.test", password="test-password-only-2026")
    def test_limite_persiste_entre_clientes(self):
        for _ in range(5):
            Client().post(reverse("login"), {"username": "admin", "password": "incorrecta"})
        self.assertEqual(Client().post(reverse("login"), {"username": "admin", "password": "test-password-only-2026"}).status_code, 429)
    def test_login_y_logout(self):
        self.assertEqual(self.client.post(reverse("login"), {"username": "admin", "password": "test-password-only-2026"}).status_code, 302)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)
        self.client.post(reverse("logout"))
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)
