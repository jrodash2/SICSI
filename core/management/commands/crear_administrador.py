from django.contrib.auth.management.commands.createsuperuser import Command as DjangoCommand
from django.db import transaction
from core.management.actor_command import ComandoConUsuario

class Command(ComandoConUsuario, DjangoCommand):
    def handle(self, *args, **options):
        from core.models import Usuario
        from core.services import auditar
        existentes = set(Usuario.objects.values_list('pk', flat=True))
        with transaction.atomic():
            resultado = super().handle(*args, **options)
            for usuario in Usuario.objects.exclude(pk__in=existentes):
                auditar('CREAR_USUARIO', 'Usuario', usuario.pk, {'username': usuario.username, 'perfil': usuario.perfil})
            return resultado
