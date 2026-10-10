from django.contrib import admin, messages
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin, TabularInline

from apps.tenants.mixins import EmpresaScopedAdminMixin
from apps.tenants.models import Empresa

from .models import ItemPedido, Pedido
from .services import EstoqueInsuficiente, reservar_estoque


class ItemPedidoInline(TabularInline):
    model = ItemPedido
    extra = 1
    fields = ("sku", "quantidade", "preco_unitario", "subtotal")
    autocomplete_fields = ("sku",)
    readonly_fields = ("subtotal",)

    def has_add_permission(self, request, obj=None):
        return bool(getattr(request.user, "is_gerente", False))

    def has_change_permission(self, request, obj=None):
        return bool(getattr(request.user, "is_gerente", False))

    def has_delete_permission(self, request, obj=None):
        return bool(getattr(request.user, "is_gerente", False))


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
    search_fields = (
        "cliente_nome",
        "cliente_documento",
        "cliente_whatsapp",
        "cliente__email",
    )
    autocomplete_fields = ("cliente",)
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
            {
                "fields": (
                    "cliente",
                    "cliente_nome",
                    "cliente_documento",
                    "cliente_whatsapp",
                )
            },
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

    # ---- Travas de segurança (RBAC) --------------------------------------
    def has_view_permission(self, request, obj=None):
        return bool(request.user.is_authenticated)

    def has_change_permission(self, request, obj=None):
        # Todos os perfis internos podem abrir o pedido para atualizar o
        # status de entrega; a edição de itens/valores é travada abaixo.
        return bool(request.user.is_authenticated)

    def has_add_permission(self, request):
        return bool(getattr(request.user, "is_gerente", False))

    def has_delete_permission(self, request, obj=None):
        return bool(getattr(request.user, "is_gerente", False))

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if not request.user.is_gerente:
            readonly += [
                "cliente",
                "cliente_nome",
                "cliente_documento",
                "cliente_whatsapp",
                "total_itens",
                "valor_total",
                "aceite_lgpd",
            ]
        return readonly

    def save_model(self, request, obj, form, change):
        """Atribui automaticamente a fábrica padrão ao cadastrar manualmente."""
        if not obj.empresa_id:
            obj.empresa = getattr(request.user, "empresa", None) or Empresa.obter_fabrica()
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        """Baixa o estoque físico dos SKUs ao criar um pedido manualmente."""
        super().save_related(request, form, formsets, change)
        if change:
            return
        itens = [
            (item.sku_id, item.quantidade)
            for item in form.instance.itens.all()
            if item.quantidade
        ]
        if not itens:
            return
        try:
            with transaction.atomic():
                reservar_estoque(itens)
        except EstoqueInsuficiente as exc:
            self.message_user(
                request,
                _(
                    "Pedido criado, porém o estoque de %(sku)s é insuficiente "
                    "(disponível: %(disponivel)s). Ajuste o saldo do SKU."
                )
                % {"sku": exc.sku, "disponivel": exc.disponivel},
                level=messages.WARNING,
            )
