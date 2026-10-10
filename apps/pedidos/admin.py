from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin, TabularInline

from apps.tenants.mixins import EmpresaScopedAdminMixin
from apps.tenants.models import Empresa

from .models import ItemPedido, Pedido


class ItemPedidoInline(TabularInline):
    model = ItemPedido
    extra = 1
    fields = ("sku", "quantidade", "preco_unitario", "subtotal")
    autocomplete_fields = ("sku",)
    readonly_fields = ("subtotal",)


@admin.register(Pedido)
class PedidoAdmin(EmpresaScopedAdminMixin, ModelAdmin):
    inlines = [ItemPedidoInline]
    list_display = (
        "id",
        "cliente_nome",
        "cliente_whatsapp",
        "total_itens",
        "valor_total",
        "status",
        "aceite_lgpd",
        "created_at",
    )
    list_display_links = ("id", "cliente_nome")
    list_filter = ("status", "aceite_lgpd")
    search_fields = ("cliente_nome", "cliente_documento", "cliente_whatsapp")
    readonly_fields = (
        "ip_aceite",
        "data_aceite",
        "versao_termos",
        "created_at",
        "updated_at",
    )
    fieldsets = (
        (
            _("Cliente"),
            {"fields": ("cliente_nome", "cliente_documento", "cliente_whatsapp")},
        ),
        (
            _("Pedido"),
            {"fields": ("total_itens", "valor_total", "status")},
        ),
        (
            _("Consentimento LGPD"),
            {"fields": ("aceite_lgpd", "ip_aceite", "data_aceite", "versao_termos")},
        ),
        (_("Auditoria"), {"fields": ("created_at", "updated_at")}),
    )

    def save_model(self, request, obj, form, change):
        """Atribui automaticamente a fábrica padrão ao cadastrar manualmente."""
        if not obj.empresa_id:
            obj.empresa = getattr(request.user, "empresa", None) or Empresa.obter_fabrica()
        super().save_model(request, obj, form, change)
