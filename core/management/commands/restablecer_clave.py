from django.contrib.auth.management.commands.changepassword import Command as DjangoCommand
from django.db import transaction
from core.management.actor_command import ComandoConUsuario

class Command(ComandoConUsuario, DjangoCommand):
    def handle(self, *args, **options):
        from core.models import Usuario
        from core.services import auditar
        anteriores = dict(Usuario.objects.values_list('pk', 'password'))
        with transaction.atomic():
            resultado = super().handle(*args, **options)
            for usuario in Usuario.objects.all():
                if anteriores.get(usuario.pk) != usuario.password:
                    auditar('RESTABLECER_CONTRASENA', 'Usuario', usuario.pk, {'username': usuario.username})
            return resultado
