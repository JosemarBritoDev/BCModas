from django.contrib import admin
from django.db.models import Count, Q
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin, TabularInline

from apps.tenants.mixins import EmpresaScopedAdminMixin
from apps.usuarios.mixins import PerfilAdminMixin

from .models import Categoria, SKU, Modelo

SWATCH_JS = "js/hex_preview.js"


class HexPreviewMixin:
    """Adiciona feedback visual instantâneo do código hexadecimal da cor."""

    class Media:
        js = (SWATCH_JS,)

    @staticmethod
    def _swatch_html(hex_value):
        hex_value = (hex_value or "").strip() or "#ffffff"
        return format_html(
            '<span data-hex-preview style="display:inline-flex;align-items:center;'
            "justify-content:center;min-width:72px;height:26px;padding:0 8px;"
            "border-radius:6px;border:1px solid #cbd5e1;background:{};font-size:11px;"
            "font-weight:600;color:#fff;text-shadow:0 1px 2px rgba(0,0,0,.55);"
            'vertical-align:middle;">{}</span>',
            hex_value,
            hex_value.upper(),
        )


class SKUInline(HexPreviewMixin, TabularInline):
    model = SKU
    extra = 1
    fields = (
        "cor_nome",
        "cor_hex",
        "cor_previa",
        "tamanho",
        "quantidade_estoque",
        "codigo_barras",
    )
    readonly_fields = ("cor_previa",)

    @admin.display(description=_("Prévia"))
    def cor_previa(self, obj):
        return self._swatch_html(getattr(obj, "cor_hex", "") or "#ffffff")


@admin.register(Categoria)
class CategoriaAdmin(PerfilAdminMixin, EmpresaScopedAdminMixin, ModelAdmin):
    perfis_negados = ("FINANCEIRO",)
    list_display = ("nome", "slug", "ordem", "ativo", "num_produtos", "empresa")
    list_editable = ("ordem", "ativo")
    list_filter = ("ativo", "empresa")
    search_fields = ("nome", "slug")
    prepopulated_fields = {"slug": ("nome",)}
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (_("Categoria"), {"fields": ("empresa", "nome", "slug", "ordem", "ativo")}),
        (_("Auditoria"), {"fields": ("created_at", "updated_at")}),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(
                _num_produtos=Count(
                    "produtos",
                    filter=Q(produtos__visivel_catalogo=True),
                    distinct=True,
                )
            )
        )

    @admin.display(description=_("Produtos"), ordering="_num_produtos")
    def num_produtos(self, obj):
        return obj._num_produtos


@admin.register(Modelo)
class ModeloAdmin(PerfilAdminMixin, EmpresaScopedAdminMixin, ModelAdmin):
    perfis_negados = ("FINANCEIRO",)
    inlines = [SKUInline]
    list_display = (
        "nome",
        "marca",
        "categoria",
        "lancamento",
        "preco_varejo",
        "preco_atacado",
        "qtd_minima_atacado",
        "visivel_catalogo",
        "empresa",
    )
    list_filter = ("visivel_catalogo", "categoria", "lancamento", "marca")
    search_fields = ("nome", "marca", "descricao")
    autocomplete_fields = ("categoria",)
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (_("Identificação"), {"fields": ("empresa", "nome", "marca", "estampa_logo")}),
        (
            _("Catálogo"),
            {"fields": ("categoria", "lancamento", "avaliacao")},
        ),
        (
            _("Comercial"),
            {
                "fields": (
                    ("preco_varejo", "preco_atacado"),
                    "qtd_minima_atacado",
                    "visivel_catalogo",
                )
            },
        ),
        (
            _("Ficha Técnica"),
            {"fields": ("composicao", "gramatura", "descricao", "tabela_medidas_json")},
        ),
        (
            _("Fotos"),
            {
                "fields": (
                    ("foto_1", "foto_2"),
                    ("foto_3", "foto_4"),
                    ("foto_5", "foto_6"),
                )
            },
        ),
        (_("Auditoria"), {"fields": ("created_at", "updated_at")}),
    )

    def get_readonly_fields(self, request, obj=None):
        readonly = list(self.readonly_fields)
        if not request.user.is_superuser and getattr(request.user, "role", None) != "SUPERADMIN":
            readonly.append("empresa")
        return readonly


@admin.register(SKU)
class SKUAdmin(HexPreviewMixin, PerfilAdminMixin, EmpresaScopedAdminMixin, ModelAdmin):
    perfis_negados = ("FINANCEIRO",)
    list_display = (
        "modelo",
        "cor_swatch",
        "tamanho",
        "quantidade_estoque",
        "codigo_barras",
        "empresa",
    )
    list_filter = ("tamanho", "cor_nome")
    search_fields = ("modelo__nome", "cor_nome", "codigo_barras")
    list_editable = ("quantidade_estoque",)
    autocomplete_fields = ("modelo",)
    readonly_fields = ("created_at", "updated_at", "cor_previa")
    fieldsets = (
        (
            _("Variação"),
            {
                "fields": (
                    "empresa",
                    "modelo",
                    "cor_nome",
                    ("cor_hex", "cor_previa"),
                    "tamanho",
                    "quantidade_estoque",
                    "codigo_barras",
                )
            },
        ),
        (_("Auditoria"), {"fields": ("created_at", "updated_at")}),
    )

    @admin.display(description=_("Cor"))
    def cor_swatch(self, obj):
        return format_html(
            '<span style="display:inline-block;width:14px;height:14px;'
            'border-radius:3px;border:1px solid #888;background:{};'
            'vertical-align:middle;margin-right:6px;"></span>{}',
            obj.cor_hex,
            obj.cor_nome,
        )

    @admin.display(description=_("Prévia da Cor"))
    def cor_previa(self, obj):
        return self._swatch_html(getattr(obj, "cor_hex", "") or "#ffffff")
