import re

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _


class ClienteManager(BaseUserManager):
    """Manager de contas de clientes do catálogo público."""

    use_in_migrations = True

    def _create_cliente(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("O e-mail é obrigatório.")
        email = self.normalize_email(email)
        cliente = self.model(email=email, **extra_fields)
        if password:
            cliente.set_password(password)
        else:
            cliente.set_unusable_password()
        cliente.save(using=self._db)
        return cliente

    def create_cliente(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_staff", False)
        return self._create_cliente(email, password, **extra_fields)


class Cliente(AbstractBaseUser):
    """Comprador identificado no catálogo público da fábrica.

    A conta é usada para autenticar o cliente no checkout, garantindo que
    os dados cadastrais fiquem vinculados ao ``Pedido`` (LGPD/auditoria).
    """

    class TipoPessoa(models.TextChoices):
        PF = "PF", _("Pessoa Física")
        PJ = "PJ", _("Pessoa Jurídica")

    ESTADOS = [
        ("AC", "Acre"), ("AL", "Alagoas"), ("AP", "Amapá"), ("AM", "Amazonas"),
        ("BA", "Bahia"), ("CE", "Ceará"), ("DF", "Distrito Federal"),
        ("ES", "Espírito Santo"), ("GO", "Goiás"), ("MA", "Maranhão"),
        ("MT", "Mato Grosso"), ("MS", "Mato Grosso do Sul"), ("MG", "Minas Gerais"),
        ("PA", "Pará"), ("PB", "Paraíba"), ("PR", "Paraná"), ("PE", "Pernambuco"),
        ("PI", "Piauí"), ("RJ", "Rio de Janeiro"), ("RN", "Rio Grande do Norte"),
        ("RS", "Rio Grande do Sul"), ("RO", "Rondônia"), ("RR", "Roraima"),
        ("SC", "Santa Catarina"), ("SP", "São Paulo"), ("SE", "Sergipe"),
        ("TO", "Tocantins"),
    ]

    empresa = models.ForeignKey(
        "tenants.Empresa",
        verbose_name=_("Empresa"),
        on_delete=models.CASCADE,
        related_name="clientes",
    )
    nome_razao_social = models.CharField(_("Nome/Razão Social"), max_length=180)
    tipo_pessoa = models.CharField(
        _("Tipo de Pessoa"),
        max_length=2,
        choices=TipoPessoa.choices,
        default=TipoPessoa.PF,
    )
    cpf_cnpj = models.CharField(_("CPF/CNPJ"), max_length=18, blank=True, default="")
    whatsapp = models.CharField(_("WhatsApp"), max_length=20)
    email = models.EmailField(_("E-mail"), unique=True)
    cep = models.CharField(_("CEP"), max_length=9, blank=True, default="")
    endereco = models.CharField(_("Endereço"), max_length=180, blank=True, default="")
    numero = models.CharField(_("Número"), max_length=20, blank=True, default="")
    bairro = models.CharField(_("Bairro"), max_length=120, blank=True, default="")
    cidade = models.CharField(_("Cidade"), max_length=120, blank=True, default="")
    estado = models.CharField(
        _("Estado"), max_length=2, choices=ESTADOS, blank=True, default=""
    )
    is_active = models.BooleanField(_("Ativo"), default=True)
    is_staff = models.BooleanField(_("Acesso Administrativo"), default=False)
    created_at = models.DateTimeField(_("Criado em"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Atualizado em"), auto_now=True)

    objects = ClienteManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["nome_razao_social", "whatsapp"]

    class Meta:
        verbose_name = _("Cliente")
        verbose_name_plural = _("Clientes")
        ordering = ["nome_razao_social"]

    def __str__(self):
        return f"{self.nome_razao_social} ({self.email})"

    @property
    def is_cliente(self):
        return True

    @property
    def primeiro_nome(self):
        return (self.nome_razao_social or self.email).split(" ")[0]

    def documento_limpo(self):
        return re.sub(r"\D", "", self.cpf_cnpj or "")
