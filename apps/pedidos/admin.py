from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin, TabularInline

from apps.tenants.mixins import EmpresaScopedAdminMixin

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
        "empresa",
        "created_at",
    )
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
        (_("Cliente"), {"fields": ("cliente_nome", "cliente_documento", "cliente_whatsapp")}),
        (_("Pedido"), {"fields": ("empresa", "total_itens", "valor_total", "status")}),
        (
            _("Consentimento LGPD"),
            {"fields": ("aceite_lgpd", "ip_aceite", "data_aceite", "versao_termos")},
        ),
        (_("Auditoria"), {"fields": ("created_at", "updated_at")}),
    )

    def get_readonly_fields(self, request, obj=None):
        readonly = list(self.readonly_fields)
        if not request.user.is_superuser and getattr(request.user, "role", None) != "SUPERADMIN":
            readonly.append("empresa")
        return readonly