from django.contrib import admin, messages
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin, TabularInline

from apps.financeiro.services import criar_conta_receber_para_pedido
from apps.tenants.mixins import EmpresaScopedAdminMixin
from apps.tenants.models import Empresa
from apps.usuarios.mixins import PerfilAdminMixin

from .models import ItemPedido, Pedido
from .services import EstoqueInsuficiente, reservar_estoque

PERFIS_VENDAS = ("SUPERADMIN", "GERENTE", "VENDAS", "COMPRAS")

CAMPOS_COMERCIAIS = (
    "cliente",
    "cliente_nome",
    "cliente_documento",
    "cliente_whatsapp",
    "total_itens",
    "valor_total",
    "forma_pagamento",
    "tipo_entrega",
    "endereco_entrega",
    "taxa_entrega",
    "aceite_lgpd",
    "status_financeiro",
)


class ItemPedidoInline(TabularInline):
    model = ItemPedido
    extra = 1
    fields = ("sku", "quantidade", "preco_unitario", "subtotal")
    # Sem autocomplete_fields para preservar os botões nativos de pop-up do SKU.
    readonly_fields = ("subtotal",)

    def has_add_permission(self, request, obj=None):
        return bool(getattr(request.user, "is_gerente", False))

    def has_change_permission(self, request, obj=None):
        return bool(getattr(request.user, "is_gerente", False))

    def has_delete_permission(self, request, obj=None):
        return bool(getattr(request.user, "is_gerente", False))


@admin.register(Pedido)
class PedidoAdmin(PerfilAdminMixin, EmpresaScopedAdminMixin, ModelAdmin):
    perfis_permitidos = PERFIS_VENDAS
    inlines = [ItemPedidoInline]
    list_display = (
        "id",
        "cliente_nome",
        "cliente_whatsapp",
        "total_itens",
        "valor_total",
        "forma_pagamento",
        "tipo_entrega",
        "status",
        "status_financeiro",
        "created_at",
    )
    list_display_links = ("id", "cliente_nome")
    list_filter = ("status", "status_financeiro", "forma_pagamento", "tipo_entrega", "aceite_lgpd")
    search_fields = (
        "cliente_nome",
        "cliente_documento",
        "cliente_whatsapp",
        "cliente__email",
    )
    # Sem autocomplete_fields para preservar os botões nativos de pop-up do Cliente.
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
            {"fields": ("total_itens", "valor_total", "status", "status_financeiro")},
        ),
        (
            _("Pagamento e Entrega"),
            {
                "fields": (
                    "forma_pagamento",
                    "tipo_entrega",
                    "endereco_entrega",
                    "taxa_entrega",
                )
            },
        ),
        (
            _("Consentimento LGPD"),
            {"fields": ("aceite_lgpd", "ip_aceite", "data_aceite", "versao_termos")},
        ),
        (_("Auditoria"), {"fields": ("created_at", "updated_at")}),
    )

    # ---- Travas de segurança (RBAC) --------------------------------------
    def has_add_permission(self, request):
        return self._perfil_autorizado(request) and bool(
            getattr(request.user, "is_gerente", False)
        )

    def has_delete_permission(self, request, obj=None):
        return self._perfil_autorizado(request) and bool(
            getattr(request.user, "is_gerente", False)
        )

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if request.user.is_gerente:
            return readonly
        # Perfis operacionais não alteram valores/dados comerciais nem a
        # liberação financeira do pedido.
        readonly += list(CAMPOS_COMERCIAIS)
        role = getattr(request.user, "role", None)
        if role == "COMPRAS":
            readonly.append("status")
        return readonly

    def save_model(self, request, obj, form, change):
        """Atribui automaticamente a fábrica padrão ao cadastrar manualmente."""
        if not obj.empresa_id:
            obj.empresa = getattr(request.user, "empresa", None) or Empresa.obter_fabrica()
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        """Baixa o estoque físico e gera a conta a receber em pedido manual."""
        super().save_related(request, form, formsets, change)
        if change:
            return
        pedido = form.instance
        criar_conta_receber_para_pedido(pedido)

        itens = [
            (item.sku_id, item.quantidade)
            for item in pedido.itens.all()
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
