from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin, TabularInline

from apps.tenants.mixins import EmpresaScopedAdminMixin

from .models import SKU, Modelo


class SKUInline(TabularInline):
    model = SKU
    extra = 1
    fields = ("cor_nome", "cor_hex", "tamanho", "quantidade_estoque", "codigo_barras")


@admin.register(Modelo)
class ModeloAdmin(EmpresaScopedAdminMixin, ModelAdmin):
    inlines = [SKUInline]
    list_display = (
        "nome",
        "marca",
        "preco_varejo",
        "preco_atacado",
        "qtd_minima_atacado",
        "visivel_catalogo",
        "empresa",
    )
    list_filter = ("visivel_catalogo", "marca")
    search_fields = ("nome", "marca", "descricao")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (_("Identificação"), {"fields": ("empresa", "nome", "marca", "estampa_logo")}),
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
class SKUAdmin(EmpresaScopedAdminMixin, ModelAdmin):
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
    readonly_fields = ("created_at", "updated_at")

    @admin.display(description=_("Cor"))
    def cor_swatch(self, obj):
        return format_html(
            '<span style="display:inline-block;width:14px;height:14px;'
            'border-radius:3px;border:1px solid #888;background:{};'
            'vertical-align:middle;margin-right:6px;"></span>{}',
            obj.cor_hex,
            obj.cor_nome,
        )