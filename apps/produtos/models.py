from django.db import models
from django.utils.translation import gettext_lazy as _


class Modelo(models.Model):
    empresa = models.ForeignKey(
        "tenants.Empresa",
        verbose_name=_("Empresa"),
        on_delete=models.CASCADE,
        related_name="modelos",
    )
    nome = models.CharField(_("Nome"), max_length=150)
    marca = models.CharField(_("Marca"), max_length=80, blank=True, default="")
    estampa_logo = models.ImageField(
        _("Estampa/Logo"), upload_to="produtos/estampas/", blank=True, null=True
    )
    preco_tabela = models.DecimalField(
        _("Preço de Tabela"), max_digits=10, decimal_places=2
    )
    composicao = models.CharField(
        _("Composição"), max_length=150, blank=True, default=""
    )
    gramatura = models.CharField(_("Gramatura"), max_length=50, blank=True, default="")
    descricao = models.TextField(_("Descrição"), blank=True, default="")
    visivel_catalogo = models.BooleanField(_("Visível no Catálogo"), default=True)
    foto_1 = models.ImageField(
        _("Foto 1"), upload_to="produtos/fotos/", blank=True, null=True
    )
    foto_2 = models.ImageField(
        _("Foto 2"), upload_to="produtos/fotos/", blank=True, null=True
    )
    foto_3 = models.ImageField(
        _("Foto 3"), upload_to="produtos/fotos/", blank=True, null=True
    )
    foto_4 = models.ImageField(
        _("Foto 4"), upload_to="produtos/fotos/", blank=True, null=True
    )
    foto_5 = models.ImageField(
        _("Foto 5"), upload_to="produtos/fotos/", blank=True, null=True
    )
    foto_6 = models.ImageField(
        _("Foto 6"), upload_to="produtos/fotos/", blank=True, null=True
    )
    tabela_medidas_json = models.JSONField(
        _("Tabela de Medidas"), default=dict, blank=True
    )
    created_at = models.DateTimeField(_("Criado em"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Atualizado em"), auto_now=True)

    class Meta:
        verbose_name = _("Modelo")
        verbose_name_plural = _("Modelos")
        ordering = ["nome"]

    def __str__(self):
        return f"{self.nome} ({self.marca})" if self.marca else self.nome


class SKU(models.Model):
    class Tamanho(models.TextChoices):
        PP = "PP", _("PP")
        P = "P", _("P")
        M = "M", _("M")
        G = "G", _("G")
        GG = "GG", _("GG")
        XG = "XG", _("XG")
        XGG = "XGG", _("XGG")

    empresa = models.ForeignKey(
        "tenants.Empresa",
        verbose_name=_("Empresa"),
        on_delete=models.CASCADE,
        related_name="skus",
    )
    modelo = models.ForeignKey(
        Modelo,
        verbose_name=_("Modelo"),
        on_delete=models.CASCADE,
        related_name="skus",
    )
    cor_nome = models.CharField(_("Cor"), max_length=60)
    cor_hex = models.CharField(_("Hex da Cor"), max_length=7, default="#000000")
    tamanho = models.CharField(
        _("Tamanho"), max_length=5, choices=Tamanho.choices, default=Tamanho.M
    )
    quantidade_estoque = models.PositiveIntegerField(_("Estoque"), default=0)
    codigo_barras = models.CharField(
        _("Código de Barras"), max_length=64, blank=True, default=""
    )
    created_at = models.DateTimeField(_("Criado em"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Atualizado em"), auto_now=True)

    class Meta:
        verbose_name = _("SKU")
        verbose_name_plural = _("SKUs")
        ordering = ["modelo", "cor_nome", "tamanho"]
        constraints = [
            models.UniqueConstraint(
                fields=["modelo", "cor_nome", "tamanho"],
                name="unique_grade_modelo_cor_tamanho",
            )
        ]

    def __str__(self):
        return f"{self.modelo.nome} | {self.cor_nome} | {self.tamanho}"

    def save(self, *args, **kwargs):
        if self.modelo_id and not self.empresa_id:
            self.empresa_id = self.modelo.empresa_id
        super().save(*args, **kwargs)