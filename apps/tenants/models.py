from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


class Plano(models.Model):
    nome = models.CharField(_("Nome"), max_length=80, unique=True)
    preco_mensal = models.DecimalField(
        _("Preço Mensal"), max_digits=10, decimal_places=2
    )
    limite_usuarios = models.PositiveIntegerField(_("Limite de Usuários"))
    limite_produtos = models.PositiveIntegerField(_("Limite de Produtos"))
    created_at = models.DateTimeField(_("Criado em"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Atualizado em"), auto_now=True)

    class Meta:
        verbose_name = _("Plano")
        verbose_name_plural = _("Planos")
        ordering = ["preco_mensal"]

    def __str__(self):
        return self.nome


class Empresa(models.Model):
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
    plano = models.ForeignKey(
        Plano,
        verbose_name=_("Plano"),
        on_delete=models.PROTECT,
        related_name="empresas",
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
        verbose_name = _("Empresa")
        verbose_name_plural = _("Empresas")
        ordering = ["nome_fantasia"]

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
