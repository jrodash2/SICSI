from concurrent.futures import ThreadPoolExecutor
from datetime import date
from io import StringIO
from pathlib import Path
import tempfile
from threading import Barrier
from unittest.mock import patch
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, SimpleTestCase, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from core.actor import contexto_usuario, usuario_actual
from core.models import ActaEntrega, Alerta, Auditoria, Gestion, Renovacion, Servicio, Usuario
from core.services import auditar, enviar_alerta
from .test_actas import docx_prueba

PASSWORD = 'test-password-only-2026'

class UsuariosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = Usuario.objects.create_superuser(username='admin', email='admin@example.test', password=PASSWORD)
        cls.gestor = Usuario.objects.create_user(username='gestor', first_name='Personal', last_name='Gestor', email='gestor@example.test', password=PASSWORD, rol='gestor')
        cls.consulta = Usuario.objects.create_user(username='consulta', email='consulta@example.test', password=PASSWORD)
        cls.servicio = Servicio.objects.create(codigo='AUD-TEST', nombre='Servicio de prueba', fecha_vencimiento=date(2026, 12, 31))
    def setUp(self):
        self.client.force_login(self.admin)
    def datos_usuario(self, **kwargs):
        data = {'username': 'nuevo', 'first_name': 'Persona', 'last_name': 'Autorizada', 'email': 'nuevo@example.test', 'rol': 'gestor', 'is_active': 'on', 'password1': 'inicial-test-clave-2026', 'password2': 'inicial-test-clave-2026'}
        data.update(kwargs)
        return data
    def servicio_data(self):
        return {'codigo': 'CREADO', 'nombre': 'Servicio registrado', 'periodicidad': 'anual', 'estado': 'Activo', 'tramite': 'Pendiente', 'fecha_vencimiento': '2026-12-31'}
    def test_administrador_crea_usuario_con_perfil_sin_exponer_clave(self):
        r = self.client.post(reverse('usuario_crear'), self.datos_usuario())
        self.assertEqual(r.status_code, 302)
        item = Usuario.objects.get(username='nuevo')
        self.assertTrue(item.check_password('inicial-test-clave-2026'))
        self.assertFalse(item.is_superuser)
        self.assertEqual(item.creado_por_id, self.admin.pk)
        evento = Auditoria.objects.get(accion='CREAR_USUARIO')
        self.assertEqual(evento.usuario_id, self.admin.pk)
        self.assertNotIn('inicial-test-clave-2026', str(evento.detalle))
        self.assertNotIn(item.password, str(evento.detalle))
    def test_no_hay_registro_publico_ni_acceso_a_usuarios_para_no_admin(self):
        self.assertEqual(Client().get(reverse('usuarios')).status_code, 302)
        self.assertEqual(Client().get('/registro/').status_code, 404)
        for user in [self.gestor, self.consulta]:
            client = Client(); client.force_login(user)
            self.assertEqual(client.get(reverse('usuarios')).status_code, 403)
            self.assertEqual(client.post(reverse('usuario_crear'), self.datos_usuario()).status_code, 403)
        self.assertFalse(Usuario.objects.filter(username='nuevo').exists())
    def test_consulta_no_modifica_y_gestor_no_abre_secciones_privadas(self):
        self.client.force_login(self.consulta)
        for name in ['servicio_crear', 'servicio_editar', 'servicio_eliminar', 'gestion_crear', 'servicio_renovar', 'documento_crear', 'alerta_urgente']:
            args = [] if name == 'servicio_crear' else [self.servicio.pk]
            self.assertEqual(self.client.post(reverse(name, args=args), self.servicio_data()).status_code, 403, name)
        self.assertEqual(Servicio.objects.count(), 1)
        self.assertNotContains(self.client.get(reverse('servicio_detalle', args=[self.servicio.pk])), 'Editar servicio')
        for user in [self.gestor, self.consulta]:
            self.client.force_login(user)
            for name in ['actas', 'acta_detalle', 'acta_descargar', 'auditoria', 'destinatarios']:
                args = [999] if name in ['acta_detalle', 'acta_descargar'] else []
                self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 403, name)
            for name in ['servicios', 'gestiones', 'reportes', 'alertas', 'dashboard']:
                self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
    def test_creador_no_se_falsifica_y_actualizacion_captura_otro_usuario(self):
        self.client.force_login(self.gestor)
        datos = self.servicio_data(); datos.update(creado_por=self.consulta.pk, creado_por_nombre='Autor falso')
        self.client.post(reverse('servicio_crear'), datos)
        item = Servicio.objects.get(codigo='CREADO')
        self.assertEqual(item.creado_por_id, self.gestor.pk)
        self.assertIn('gestor', item.autor_creacion)
        self.assertNotIn('Autor falso', item.autor_creacion)
        self.client.force_login(self.admin)
        datos['nombre'] = 'Modificado'; datos['version'] = item.version
        self.client.post(reverse('servicio_editar', args=[item.pk]), datos)
        item.refresh_from_db()
        self.assertEqual(item.creado_por_id, self.gestor.pk)
        self.assertEqual(item.actualizado_por_id, self.admin.pk)
        self.assertEqual(Auditoria.objects.get(accion='EDITAR',registro_id=item.pk).usuario_id, self.admin.pk)
        self.assertContains(self.client.get(reverse('servicio_detalle', args=[item.pk])), 'Última modificación por')
    def test_gestiones_y_renovaciones_identifican_al_usuario(self):
        self.client.force_login(self.gestor)
        self.client.post(reverse('gestion_crear', args=[self.servicio.pk]), {'fecha':'2026-11-16', 'tipo':'Seguimiento', 'descripcion':'Consulta', 'tramite':'En trámite'})
        self.assertEqual(Gestion.objects.get().creado_por_id, self.gestor.pk)
        self.client.post(reverse('servicio_renovar', args=[self.servicio.pk]), {'nuevo_inicio':'2027-01-01','nuevo_vencimiento':'2027-12-31'})
        self.assertEqual(Renovacion.objects.get().creado_por_id, self.gestor.pk)
        self.servicio.refresh_from_db()
        self.assertEqual(self.servicio.actualizado_por_id, self.gestor.pk)
        self.assertTrue(all(e.usuario_id == self.gestor.pk for e in Auditoria.objects.filter(accion__in=['REGISTRAR_GESTION','RENOVAR'])))
    def test_autor_historico_se_conserva_si_cambia_nombre_de_usuario(self):
        self.client.force_login(self.gestor)
        self.client.post(reverse('servicio_crear'), self.servicio_data())
        item = Servicio.objects.get(codigo='CREADO')
        nombre = item.autor_creacion
        Usuario.objects.filter(pk=self.gestor.pk).update(username='gestor_renombrado', first_name='Otro nombre')
        item.refresh_from_db()
        self.assertEqual(item.autor_creacion, nombre)
        self.assertIn('gestor', Auditoria.objects.get(accion='CREAR',registro_id=item.pk).usuario_nombre)
    def test_no_se_desactiva_ni_se_degrada_la_cuenta_actual(self):
        self.client.post(reverse('usuario_estado', args=[self.admin.pk]))
        data = self.datos_usuario(username=self.admin.username,email=self.admin.email,rol='consulta')
        response = self.client.post(reverse('usuario_editar', args=[self.admin.pk]), data)
        self.assertContains(response,'quitarte el perfil de administrador')
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.es_administrador)
    def test_desactivar_revoca_sesion_y_preserva_registros(self):
        cliente = Client(); cliente.force_login(self.gestor)
        cliente.post(reverse('servicio_crear'), self.servicio_data())
        self.client.post(reverse('usuario_estado', args=[self.gestor.pk]))
        self.assertEqual(cliente.get(reverse('dashboard')).status_code,302)
        self.assertTrue(Servicio.objects.filter(creado_por=self.gestor).exists())
    def test_restablecer_clave_invalida_sesiones_y_no_registra_secreto(self):
        cliente = Client(); cliente.force_login(self.gestor)
        clave = 'restablecida-test-segura-2026'
        response = self.client.post(reverse('usuario_password',args=[self.gestor.pk]),{'new_password1':clave,'new_password2':clave})
        self.assertEqual(response.status_code,302)
        self.assertEqual(cliente.get(reverse('dashboard')).status_code,302)
        audit = Auditoria.objects.get(accion='RESTABLECER_CONTRASENA')
        self.assertEqual(audit.usuario_id,self.admin.pk)
        self.assertNotIn(clave,str(audit.detalle))
    def test_login_y_logout_atribuyen_el_id_real(self):
        client = Client()
        self.assertEqual(client.post(reverse('login'),{'username':'GESTOR','password':PASSWORD}).status_code,302)
        self.assertEqual(Auditoria.objects.get(accion='INICIAR_SESION').usuario_id,self.gestor.pk)
        client.post(reverse('logout'))
        self.assertEqual(Auditoria.objects.get(accion='CERRAR_SESION').usuario_id,self.gestor.pk)
    def test_auditoria_exportaciones_captura_usuario_y_no_filtra_secciones_privadas(self):
        self.client.force_login(self.consulta)
        self.assertEqual(self.client.get(reverse('exportar',args=['xlsx'])).status_code,200)
        audit = Auditoria.objects.get(accion='EXPORTAR')
        self.assertEqual(audit.usuario_id,self.consulta.pk)
        self.assertEqual(audit.origen,'web')
        response = self.client.get(reverse('dashboard'))
        self.assertNotContains(response,'href="/usuarios/"')
        self.assertNotContains(response,'href="/destinatarios/"')
    def test_importacion_local_guarda_responsable_y_origen(self):
        with tempfile.TemporaryDirectory() as root, override_settings(PRIVATE_MEDIA_ROOT=Path(root)/'privado'):
            path = Path(root)/'acta.docx'; path.write_bytes(docx_prueba())
            call_command('importar_acta',str(path),aplicar=True,usuario=self.admin.username,stdout=StringIO())
            acta = ActaEntrega.objects.get()
            self.assertEqual(acta.creado_por_id,self.admin.pk)
            self.assertEqual(acta.origen_registro,'consola')
            self.assertTrue(all(s.creado_por_id==self.admin.pk for s in acta.servicios.all()))
            self.assertEqual(Auditoria.objects.get(accion='IMPORTAR_ACTA').usuario_id,self.admin.pk)
            with self.assertRaises(CommandError):
                call_command('importar_acta',str(path),aplicar=True,usuario=self.gestor.username,stdout=StringIO())
    @patch('core.services.entregar',return_value=('Enviada','250 OK'))
    def test_cron_se_distingue_de_accion_web_y_notifica_admins_activos(self,smtp):
        extra=Usuario.objects.create_superuser(username='admin_dos',email='admin-dos@example.test',password=PASSWORD)
        with contexto_usuario(None,'sistema'):
            enviar_alerta(self.servicio.pk,'45',date(2026,11,16))
        alerta=Alerta.objects.get()
        self.assertIsNone(alerta.creado_por_id)
        self.assertEqual(alerta.origen_registro,'sistema')
        self.assertCountEqual([call.args[2] for call in smtp.call_args_list],[self.admin.email,extra.email])
        self.assertIsNone(Auditoria.objects.get(accion='PROCESAR_ALERTA').usuario_id)
    def test_formulario_y_modulo_institucional_renderizan(self):
        for name,args in [('usuarios',[]),('usuario_crear',[]),('usuario_editar',[self.gestor.pk]),('usuario_password',[self.gestor.pk])]:
            self.assertEqual(self.client.get(reverse(name,args=args)).status_code,200)
        response=self.client.get(reverse('servicio_crear'))
        self.assertContains(response,'1. Identificación del servicio')
        self.assertContains(response,'3. Contratación y vigencia')
        self.assertContains(response,'institucional.css')
    def test_cambio_automatico_no_se_atribuye_al_ultimo_usuario_humano(self):
        with contexto_usuario(self.admin,'web'):
            servicio=Servicio.objects.create(codigo='AUTO',nombre='Registro inicial')
        servicio.nombre='Cambio automático'
        servicio.save()
        servicio.refresh_from_db()
        self.assertEqual(servicio.creado_por_id,self.admin.pk)
        self.assertIsNone(servicio.actualizado_por_id)
        self.assertEqual(servicio.origen_actualizacion,'sistema')
        self.assertIn('Sistema',servicio.autor_actualizacion)

    def test_creacion_fuera_de_sesion_no_hereda_el_actor_anterior(self):
        self.client.get(reverse('dashboard'))
        self.assertIsNone(usuario_actual())
        item=Servicio.objects.create(codigo='FUERA',nombre='Proceso automático')
        self.assertIsNone(item.creado_por_id)
        with self.assertRaises(RuntimeError):
            with contexto_usuario(self.admin,'web'):
                raise RuntimeError('Interrupción simulada')
        self.assertIsNone(usuario_actual())

    @patch.dict('os.environ', {'DJANGO_SUPERUSER_PASSWORD': 'clave-bootstrap-test-2026'})
    def test_crear_administrador_por_consola_con_actor(self):
        call_command('crear_administrador', username='admin_consola', email='consola@example.test', interactive=False, usuario=self.admin.username, stdout=StringIO())
        usuario=Usuario.objects.get(username='admin_consola')
        self.assertTrue(usuario.es_administrador)
        self.assertEqual(usuario.creado_por_id,self.admin.pk)
        evento=Auditoria.objects.get(accion='CREAR_USUARIO',registro_id=usuario.pk)
        self.assertEqual(evento.usuario_id,self.admin.pk)
        self.assertEqual(evento.origen,'consola')

    @patch('core.management.commands.restablecer_clave.Command._get_pass',return_value='clave-consola-test-2026')
    def test_restablecer_por_consola_no_pierde_al_responsable(self,getpass):
        call_command('restablecer_clave',self.gestor.username,usuario=self.admin.username,stdout=StringIO())
        self.gestor.refresh_from_db()
        self.assertTrue(self.gestor.check_password('clave-consola-test-2026'))
        evento=Auditoria.objects.get(accion='RESTABLECER_CONTRASENA')
        self.assertEqual(evento.usuario_id,self.admin.pk)
        self.assertNotIn('clave-consola-test-2026',str(evento.detalle))


class ContextosConcurrentesTests(SimpleTestCase):
    def test_dos_solicitudes_no_comparten_usuario(self):
        barrera=Barrier(2)
        def ejecutar(nombre):
            usuario=Usuario(username=nombre)
            with contexto_usuario(usuario,'web'):
                barrera.wait(timeout=5)
                return usuario_actual().username
        with ThreadPoolExecutor(max_workers=2) as pool:
            resultados=list(pool.map(ejecutar,['persona_a','persona_b']))
        self.assertEqual(resultados,['persona_a','persona_b'])
        self.assertIsNone(usuario_actual())

class ActualizacionUsuariosTests(TransactionTestCase):
    def test_migracion_conserva_administrador_y_reinicia_secuencia_sin_asignar_historia(self):
        executor=MigrationExecutor(connection)
        antes=[('core','0003_alter_alerta_estado_destinatarioalerta_envioalerta')]
        despues=[('core','0005_actaentrega_origen_actualizacion_and_more')]
        executor.migrate(antes)
        apps=executor.loader.project_state(antes).apps
        OldUser=apps.get_model('core','Usuario')
        OldService=apps.get_model('core','Servicio')
        from django.contrib.auth.hashers import make_password
        OldUser.objects.create(id=1,username='previo',email='previo@example.test',password=make_password(PASSWORD),is_superuser=True,is_staff=True,is_active=True)
        servicio=OldService.objects.create(codigo='PREVIO',nombre='Dato anterior')
        try:
            executor=MigrationExecutor(connection); executor.migrate(despues)
            previo=Usuario.objects.get(pk=1)
            self.assertTrue(previo.check_password(PASSWORD))
            self.assertTrue(previo.es_administrador)
            self.assertEqual(previo.rol,'administrador')
            nuevo=Usuario.objects.create_user(username='posterior',email='posterior@example.test',password=PASSWORD)
            self.assertGreater(nuevo.pk,1)
            anterior=Servicio.objects.get(pk=servicio.pk)
            self.assertIsNone(anterior.creado_por_id)
            self.assertEqual(anterior.origen_registro,'historico')
        finally:
            MigrationExecutor(connection).migrate(despues)
