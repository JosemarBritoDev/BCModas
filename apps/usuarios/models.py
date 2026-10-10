from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


class Usuario(AbstractUser):
    class Role(models.TextChoices):
        SUPERADMIN = "SUPERADMIN", _("Superadmin")
        GERENTE = "GERENTE", _("Gerente")
        COMPRAS = "COMPRAS", _("Compras")
        VENDAS = "VENDAS", _("Vendas")
        FINANCEIRO = "FINANCEIRO", _("Financeiro")

    empresa = models.ForeignKey(
        "tenants.Empresa",
        verbose_name=_("Empresa"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="usuarios",
    )
    role = models.CharField(
        _("Perfil de Acesso"),
        max_length=20,
        choices=Role.choices,
        default=Role.VENDAS,
    )

    class Meta:
        verbose_name = _("Usuário")
        verbose_name_plural = _("Usuários")

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def is_gerente(self):
        """Perfis autorizados a editar itens/valores e dados cadastrais."""
        return bool(
            self.is_superuser
            or self.role in {self.Role.GERENTE, self.Role.SUPERADMIN}
        )