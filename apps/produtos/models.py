from decimal import Decimal

from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


class Categoria(models.Model):
    """Categoria comercial de produtos da empresa.

    Substitui o antigo campo de escolhas fixas no Modelo, permitindo que cada
    empresa gerencie livremente o seu menu de navegação do catálogo. Categorias
    sem produtos ativos vinculados são automaticamente ocultadas no catálogo.
    """

    empresa = models.ForeignKey(
        "tenants.Empresa",
        verbose_name=_("Empresa"),
        on_delete=models.CASCADE,
        related_name="categorias",
    )
    nome = models.CharField(_("Nome"), max_length=80)
    slug = models.SlugField(
        _("Slug"),
        max_length=90,
        blank=True,
        help_text=_("Identificador amigável usado na URL do catálogo."),
    )
    ordem = models.PositiveIntegerField(
        _("Ordem"), default=0, help_text=_("Menor valor aparece primeiro no menu.")
    )
    ativo = models.BooleanField(
        _("Ativa"), default=True, help_text=_("Categorias inativas não são exibidas.")
    )
    created_at = models.DateTimeField(_("Criado em"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Atualizado em"), auto_now=True)

    class Meta:
        verbose_name = _("Categoria")
        verbose_name_plural = _("Categorias")
        ordering = ["ordem", "nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["empresa", "slug"], name="unique_categoria_empresa_slug"
            )
        ]

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nome)[:90]
        super().save(*args, **kwargs)


class Modelo(models.Model):
    empresa = models.ForeignKey(
        "tenants.Empresa",
        verbose_name=_("Empresa"),
        on_delete=models.CASCADE,
        related_name="modelos",
    )
    nome = models.CharField(_("Nome"), max_length=150)
    marca = models.CharField(_("Marca"), max_length=80, blank=True, default="")
    categoria = models.ForeignKey(
        Categoria,
        verbose_name=_("Categoria"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="produtos",
        help_text=_("Utilizada no menu de navegação do catálogo público."),
    )
    lancamento = models.BooleanField(
        _("Lançamento"),
        default=False,
        help_text=_("Exibe o selo LANÇAMENTO e o destaque no menu de navegação."),
    )
    avaliacao = models.DecimalField(
        _("Avaliação"),
        max_digits=2,
        decimal_places=1,
        default=Decimal("4.5"),
        help_text=_("Nota de 0,0 a 5,0 exibida por estrelas no catálogo."),
    )
    estampa_logo = models.ImageField(
        _("Estampa/Logo"), upload_to="produtos/estampas/", blank=True, null=True
    )
    preco_varejo = models.DecimalField(
        _("Preço Varejo"),
        max_digits=10,
        decimal_places=2,
        help_text=_("Valor da peça avulsa (venda no varejo)."),
    )
    preco_atacado = models.DecimalField(
        _("Preço Atacado"),
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text=_("Valor promocional por peça a partir da quantidade mínima de atacado."),
    )
    qtd_minima_atacado = models.PositiveIntegerField(
        _("Qtd. Mínima Atacado"),
        default=6,
        help_text=_("Quantidade mínima do item para aplicar o preço de atacado."),
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

    @property
    def tem_atacado(self):
        """Indica se o modelo possui preço de atacado configurado."""
        return self.preco_atacado and self.preco_atacado > 0

    def preco_unitario_para(self, quantidade):
        """Retorna o preço unitário aplicável à quantidade informada.

        Aplica o preço de atacado quando a quantidade atinge a quantidade
        mínima configurada e existe um preço de atacado cadastrado. Caso
        contrário, retorna o preço de varejo.
        """
        qtd = int(quantidade or 0)
        if self.tem_atacado and qtd >= self.qtd_minima_atacado:
            return self.preco_atacado
        return self.preco_varejo

    @property
    def fotos_urls(self):
        """URLs das fotos do modelo.

        Aceita tanto arquivos enviados (armazenados no MEDIA) quanto URLs
        externas (ex.: imagens de demonstração do Unsplash/placeholder),
        gravadas diretamente no campo ``foto_*``.
        """
        urls = []
        for indice in range(1, 7):
            imagem = getattr(self, f"foto_{indice}", None)
            if not imagem:
                continue
            nome = getattr(imagem, "name", "") or ""
            if nome.startswith(("http://", "https://")):
                urls.append(nome)
            else:
                urls.append(imagem.url)
        return urls


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