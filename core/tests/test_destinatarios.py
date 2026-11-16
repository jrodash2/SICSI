from datetime import date
from unittest.mock import patch
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from core.models import Alerta, Auditoria, DestinatarioAlerta, EnvioAlerta, Servicio, Usuario
from core.services import enviar_alerta

class DestinatariosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = Usuario.objects.create_superuser(username='admin', email='admin@example.test', password='test-password-only-2026')
        cls.servicio = Servicio.objects.create(codigo='MAIL-TEST', nombre='Servicio de prueba', fecha_vencimiento=date(2026, 12, 31))
    def setUp(self):
        self.client.force_login(self.admin)
    def test_vista_y_formulario_requieren_sesion(self):
        for name in ['destinatarios', 'destinatario_crear']:
            self.assertEqual(Client().get(reverse(name)).status_code, 302)
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        self.assertContains(self.client.get(reverse('destinatarios')), 'Administrador incluido')
    def test_alta_edicion_y_duplicado_sin_distinguir_mayusculas(self):
        r = self.client.post(reverse('destinatario_crear'), {'nombre': 'Compras', 'correo': 'COMPRAS@example.test', 'activo': 'on'})
        self.assertEqual(r.status_code, 302)
        item = DestinatarioAlerta.objects.get()
        self.assertEqual(item.correo, 'compras@example.test')
        r = self.client.post(reverse('destinatario_crear'), {'correo': 'Compras@example.test', 'activo': 'on'})
        self.assertContains(r, 'ya está registrado')
        self.assertEqual(DestinatarioAlerta.objects.count(), 1)
        self.client.post(reverse('destinatario_editar', args=[item.pk]), {'nombre': 'Compras actualizado', 'correo': item.correo, 'activo': 'on'})
        item.refresh_from_db()
        self.assertEqual(item.nombre, 'Compras actualizado')
        audit = Auditoria.objects.get(accion='EDITAR_DESTINATARIO')
        self.assertEqual(audit.detalle['anterior']['nombre'], 'Compras')
    def test_base_rechaza_correo_duplicado(self):
        DestinatarioAlerta.objects.create(correo='dup@example.test')
        with self.assertRaises(IntegrityError), transaction.atomic():
            DestinatarioAlerta.objects.create(correo='DUP@example.test')
    def test_cambio_estado_solo_post_con_csrf(self):
        item = DestinatarioAlerta.objects.create(correo='contacto@example.test')
        url = reverse('destinatario_estado', args=[item.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.admin)
        self.assertEqual(protected.post(url).status_code, 403)
        self.client.post(url)
        item.refresh_from_db()
        self.assertFalse(item.activo)
    @patch('core.services.entregar', return_value=('Enviada', '250 OK'))
    def test_envia_a_admin_y_activos_y_deduplica(self, smtp):
        DestinatarioAlerta.objects.create(correo='ADMIN@example.test')
        DestinatarioAlerta.objects.create(correo='compras@example.test', nombre='Compras')
        DestinatarioAlerta.objects.create(correo='inactivo@example.test', activo=False)
        self.assertEqual(enviar_alerta(self.servicio.pk, '45', date(2026, 11, 16)), 'enviada')
        self.assertEqual(smtp.call_count, 2)
        self.assertCountEqual([c.args[2] for c in smtp.call_args_list], ['admin@example.test', 'compras@example.test'])
        self.assertEqual(EnvioAlerta.objects.count(), 2)
        self.assertTrue(all(e.enviada for e in EnvioAlerta.objects.all()))
        self.assertEqual(enviar_alerta(self.servicio.pk, '45', date(2026, 11, 16)), 'omitida')
        self.assertEqual(smtp.call_count, 2)
    @patch('core.services.entregar')
    def test_fallo_parcial_continua_y_no_reenvia_exitosos(self, smtp):
        DestinatarioAlerta.objects.create(correo='fallo@example.test')
        DestinatarioAlerta.objects.create(correo='otro@example.test')
        def enviar(asunto, texto, correo):
            if correo == 'fallo@example.test':
                raise OSError('SMTP interrumpido')
            return 'Enviada', '250 OK'
        smtp.side_effect = enviar
        self.assertEqual(enviar_alerta(self.servicio.pk, '45', date(2026, 11, 16)), 'parcial')
        self.assertEqual(Alerta.objects.get().estado, 'Parcial')
        self.assertEqual(EnvioAlerta.objects.filter(estado='Enviada').count(), 2)
        self.assertEqual(EnvioAlerta.objects.filter(estado='Fallida o incierta').count(), 1)
        self.assertEqual(enviar_alerta(self.servicio.pk, '45', date(2026, 11, 16)), 'omitida')
        self.assertEqual(smtp.call_count, 3)
    @patch('core.services.entregar', return_value=('Enviada', '250 OK'))
    def test_eliminar_contacto_conserva_historial_y_nuevos_no_son_retroactivos(self, smtp):
        item = DestinatarioAlerta.objects.create(correo='con-historial@example.test')
        enviar_alerta(self.servicio.pk, '45', date(2026, 11, 16))
        self.client.post(reverse('destinatario_eliminar', args=[item.pk]))
        self.assertTrue(EnvioAlerta.objects.filter(correo='con-historial@example.test').exists())
        DestinatarioAlerta.objects.create(correo='nuevo@example.test')
        enviar_alerta(self.servicio.pk, '45', date(2026, 11, 16))
        self.assertEqual(smtp.call_count, 2)
    @patch('core.services.entregar', return_value=('Simulada', 'Consola, sin SMTP real'))
    def test_simulacion_no_se_marca_como_envio_real(self, smtp):
        DestinatarioAlerta.objects.create(correo='otro@example.test')
        self.assertEqual(enviar_alerta(self.servicio.pk, '45', date(2026, 11, 16)), 'simulada')
        self.assertEqual(Alerta.objects.get().estado, 'Simulada')
        self.assertFalse(EnvioAlerta.objects.filter(enviada__isnull=False).exists())
    @patch('core.mail.entregar', return_value=('Enviada', '250 Test accepted'))
    def test_prueba_solo_envia_al_confirmar_post_sin_crear_alerta(self, smtp):
        item = DestinatarioAlerta.objects.create(correo='prueba@example.test')
        url = reverse('correo_prueba', args=[item.pk])
        self.client.get(reverse('destinatarios'))
        self.assertFalse(smtp.called)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertFalse(smtp.called)
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertEqual(smtp.call_args.args[2], item.correo)
        self.assertFalse(Alerta.objects.exists())
        self.assertTrue(Auditoria.objects.filter(accion='PROBAR_CORREO').exists())
    @patch('core.mail.entregar', return_value=('Simulada', 'No SMTP'))
    def test_prueba_al_administrador_sin_contactos_adicionales(self, smtp):
        self.client.post(reverse('correo_prueba_admin'))
        self.assertEqual(smtp.call_args.args[2], self.admin.email)
    @override_settings(EMAIL_HOST_PASSWORD='smtp-key-test-only')
    @patch('core.services.entregar', side_effect=RuntimeError('fallo smtp-key-test-only'))
    def test_error_no_guarda_el_secreto_smtp(self, smtp):
        enviar_alerta(self.servicio.pk, '45', date(2026, 11, 16))
        self.assertNotIn('smtp-key-test-only', EnvioAlerta.objects.get().respuesta)
        self.assertNotIn('smtp-key-test-only', Alerta.objects.get().respuesta)
    def test_dashboard_presenta_graficos_con_datos_reales(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Renovaciones completadas')
        self.assertContains(response, 'Vencimientos por período')
        self.assertEqual(len(response.context['barras']), 6)
        self.assertTrue(all(barra['total'] == 0 for barra in response.context['barras']))
        self.assertEqual(sum(s['cantidad'] for s in response.context['segmentos']), response.context['calculables'])
