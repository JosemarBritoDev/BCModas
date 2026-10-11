from decimal import Decimal

from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


class Empresa(models.Model):
    """Dados da fábrica (instância única do ERP)."""
    class Status(models.TextChoices):
        ATIVO = "ATIVO", _("Ativo")
        SUSPENSO = "SUSPENSO", _("Suspenso")

    nome_fantasia = models.CharField(_("Nome Fantasia"), max_length=150)
    cnpj = models.CharField(_("CNPJ"), max_length=18, unique=True)
    slug = models.SlugField(
        _("Slug do Catálogo"),
        max_length=150,
        unique=True,
        blank=True,
        help_text=_(
            "Identificador público do catálogo (ex.: minha-marca). "
            "Gerado automaticamente a partir do nome fantasia."
        ),
    )
    cor_primaria = models.CharField(
        _("Cor Primária"),
        max_length=7,
        default="#111827",
        help_text=_("Cor da marca no catálogo público, em hexadecimal (ex.: #111827)."),
    )
    logo = models.ImageField(
        _("Logo"), upload_to="empresas/logo/", blank=True, null=True
    )
    favicon = models.ImageField(
        _("Favicon"), upload_to="empresas/favicon/", blank=True, null=True
    )
    email = models.EmailField(_("E-mail"))
    whatsapp_comercial = models.CharField(_("WhatsApp Comercial"), max_length=20)
    instagram = models.CharField(
        _("Instagram"), max_length=80, blank=True, default=""
    )
    endereco_origem = models.TextField(_("Endereço de Origem"), blank=True, default="")
    taxa_entrega_padrao = models.DecimalField(
        _("Taxa de Entrega Padrão"),
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text=_(
            "Valor aplicado quando o cliente escolhe 'Entrega a Combinar'. "
            "0,00 = taxa a combinar no WhatsApp."
        ),
    )
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=Status.choices,
        default=Status.ATIVO,
    )
    termos_uso = models.TextField(_("Termos de Uso"), blank=True, default="")
    politica_privacidade = models.TextField(
        _("Política de Privacidade"), blank=True, default=""
    )
    created_at = models.DateTimeField(_("Criado em"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Atualizado em"), auto_now=True)

    class Meta:
        verbose_name = _("Dados da Confecção")
        verbose_name_plural = _("Dados da Confecção")
        ordering = ["nome_fantasia"]

    @classmethod
    def obter_fabrica(cls):
        """Retorna a instância única da fábrica (a primeira ativa ou a primeira)."""
        return cls.objects.filter(status=cls.Status.ATIVO).order_by("pk").first() or cls.objects.order_by("pk").first()

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.nome_fantasia) or "confeccao"
            slug, tentativa = base, 1
            while (
                Empresa.objects.filter(slug=slug).exclude(pk=self.pk).exists()
            ):
                tentativa += 1
                slug = f"{base}-{tentativa}"
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def caminho_catalogo(self):
        """Caminho público do catálogo white-label desta confecção."""
        from django.urls import reverse

        return reverse("catalogo_publico", kwargs={"slug": self.slug})

    def __str__(self):
        return self.nome_fantasia
