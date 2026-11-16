from django.core.management.base import BaseCommand, CommandError
from core.actor import contexto_usuario

class ComandoConUsuario(BaseCommand):
    origen_comando = "consola"
    requiere_administrador = True
    registrar_finalizacion = False
    def create_parser(self, prog_name, subcommand, **kwargs):
        parser = super().create_parser(prog_name, subcommand, **kwargs)
        parser.add_argument("--usuario", help="Usuario activo responsable de la ejecución local; no equivale a un inicio de sesión web.")
        return parser
    def execute(self, *args, **options):
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor
        from django.db.utils import DatabaseError
        try:
            executor = MigrationExecutor(connection)
            if executor.migration_plan(executor.loader.graph.leaf_nodes()):
                raise CommandError("Hay migraciones pendientes. Ejecute python manage.py migrate antes de este proceso.")
        except DatabaseError as exc:
            raise CommandError("No se pudo preparar la auditoría. Revise PostgreSQL y ejecute python manage.py migrate.") from exc
        usuario = None
        if options.get("usuario"):
            from core.models import Usuario
            usuario = Usuario.objects.filter(username__iexact=options["usuario"], is_active=True).first()
            if usuario is None or (self.requiere_administrador and not usuario.es_administrador) or (not self.requiere_administrador and not usuario.puede_editar):
                raise CommandError("El usuario responsable no existe, está inactivo o no tiene permisos para este proceso.")
        with contexto_usuario(usuario, "consola" if usuario else self.origen_comando):
            resultado = super().execute(*args, **options)
            if self.registrar_finalizacion:
                from core.services import auditar
                auditar("PROCESO_CONSOLA", "Comando", detalle={"comando": self.__module__.rsplit(".", 1)[-1]})
            return resultado
