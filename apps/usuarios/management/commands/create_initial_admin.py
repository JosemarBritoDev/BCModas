import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

DEFAULT_PASSWORD = os.environ.get("DJANGO_INITIAL_ADMIN_PASSWORD", "Admin123!")


class Command(BaseCommand):
    help = (
        "Cria o superusuário padrão do painel BC Modas "
        "(josemar / ti.josemarbrito@gmail.com / SUPERADMIN), se não existir."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default=DEFAULT_PASSWORD,
            help=f"Senha do superusuário (padrão: {DEFAULT_PASSWORD}).",
        )

    def handle(self, *args, **options):
        Usuario = get_user_model()

        usuario, criado = Usuario.objects.get_or_create(
            username="josemar",
            defaults={
                "email": "ti.josemarbrito@gmail.com",
                "role": Usuario.Role.SUPERADMIN,
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
            },
        )

        usuario.email = "ti.josemarbrito@gmail.com"
        usuario.role = Usuario.Role.SUPERADMIN
        usuario.is_staff = True
        usuario.is_superuser = True
        usuario.is_active = True
        usuario.set_password(options["password"])
        usuario.save()

        acao = "criado" if criado else "atualizado"
        self.stdout.write(
            self.style.SUCCESS(
                f"Superusuário '{usuario.username}' {acao} com sucesso "
                f"(role={usuario.role}, superuser={usuario.is_superuser})."
            )
        )