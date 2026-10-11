from django.contrib import admin, messages
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin, TabularInline

from apps.tenants.mixins import EmpresaScopedAdminMixin
from apps.usuarios.mixins import PerfilAdminMixin

from .models import CaixaDiario, CaixaMovimentacao, ContaPagar, ContaReceber
from .services import registrar_pagamento, registrar_recebimento

PERFIS_FINANCEIRO = ("SUPERADMIN", "GERENTE", "FINANCEIRO")


class _FinanceiroBaseAdmin(PerfilAdminMixin, EmpresaScopedAdminMixin, ModelAdmin):
    perfis_permitidos = PERFIS_FINANCEIRO
    list_per_page = 30


# ─────────────────────────────────────────────────────────────────────────────
# Contas a Pagar
# ─────────────────────────────────────────────────────────────────────────────
@admin.register(ContaPagar)
class ContaPagarAdmin(_FinanceiroBaseAdmin):
    list_display = (
        "descricao",
        "fornecedor",
        "categoria",
        "valor",
        "data_vencimento",
        "status",
        "esta_atrasada",
    )
    list_filter = ("status", "categoria")
    search_fields = ("descricao", "fornecedor")
    date_hierarchy = "data_vencimento"
    readonly_fields = ("esta_atrasada", "created_at", "updated_at")
    actions = ("acao_marcar_pago", "acao_marcar_pendente", "acao_cancelar")
    fieldsets = (
        (
            _("Conta"),
            {"fields": ("empresa", "fornecedor", "categoria", "descricao", "valor")},
        ),
        (
            _("Pagamento"),
            {
                "fields": (
                    ("data_vencimento", "data_pagamento"),
                    "status",
                    "esta_atrasada",
                    "comprovante",
                )
            },
        ),
        (_("Observações"), {"fields": ("observacoes",)}),
        (_("Auditoria"), {"fields": ("created_at", "updated_at")}),
    )

    @admin.display(boolean=True, description=_("Atrasada?"))
    def esta_atrasada(self, obj):
        return obj.esta_atrasada if obj else False

    @admin.action(description=_("Marcar selecionadas como PAGO"))
    def acao_marcar_pago(self, request, queryset):
        total = 0
        for conta in queryset:
            registrar_pagamento(conta, operador=request.user)
            total += 1
        self.message_user(request, _("%(n)s conta(s) marcada(s) como paga(s).") % {"n": total})

    @admin.action(description=_("Devolver para PENDENTE"))
    def acao_marcar_pendente(self, request, queryset):
        queryset.update(status=ContaPagar.Status.PENDENTE, data_pagamento=None)
        self.message_user(request, _("Contas reabertas como pendentes."))

    @admin.action(description=_("Cancelar selecionadas"))
    def acao_cancelar(self, request, queryset):
        queryset.update(status=ContaPagar.Status.CANCELADO)
        self.message_user(request, _("Contas canceladas."))


# ─────────────────────────────────────────────────────────────────────────────
# Contas a Receber
# ─────────────────────────────────────────────────────────────────────────────
@admin.register(ContaReceber)
class ContaReceberAdmin(_FinanceiroBaseAdmin):
    list_display = (
        "cliente_nome",
        "origem",
        "pedido",
        "valor",
        "forma_pagamento",
        "data_vencimento",
        "status",
        "esta_atrasada",
    )
    list_filter = ("status", "origem", "forma_pagamento")
    search_fields = ("cliente_nome", "descricao", "pedido__id")
    # Sem autocomplete_fields para preservar os botões nativos de pop-up.
    date_hierarchy = "data_vencimento"
    readonly_fields = ("esta_atrasada", "created_at", "updated_at")
    actions = ("acao_marcar_recebido", "acao_marcar_faturado", "acao_cancelar")
    fieldsets = (
        (
            _("Recebimento"),
            {
                "fields": (
                    "empresa",
                    "origem",
                    "pedido",
                    "cliente",
                    "cliente_nome",
                    "descricao",
                )
            },
        ),
        (
            _("Valores e Pagamento"),
            {
                "fields": (
                    "valor",
                    ("data_vencimento", "data_recebimento"),
                    "forma_pagamento",
                    "status",
                    "esta_atrasada",
                    "comprovante",
                )
            },
        ),
        (_("Observações"), {"fields": ("observacoes",)}),
        (_("Auditoria"), {"fields": ("created_at", "updated_at")}),
    )

    @admin.display(boolean=True, description=_("Atrasada?"))
    def esta_atrasada(self, obj):
        return obj.esta_atrasada if obj else False

    def save_model(self, request, obj, form, change):
        if not obj.cliente_nome and obj.cliente_id:
            obj.cliente_nome = obj.cliente.nome_razao_social
        if not obj.cliente_nome:
            obj.cliente_nome = _("Origem Externa")
        super().save_model(request, obj, form, change)

    @admin.action(description=_("Confirmar pagamento/liberação do pedido"))
    def acao_marcar_recebido(self, request, queryset):
        total = 0
        for conta in queryset:
            registrar_recebimento(conta, operador=request.user)
            total += 1
        self.message_user(
            request,
            _("%(n)s conta(s) recebida(s) e pedido(s) liberado(s).") % {"n": total},
        )

    @admin.action(description=_("Aprovar faturamento atacado"))
    def acao_marcar_faturado(self, request, queryset):
        for conta in queryset:
            conta.status = ContaReceber.Status.FATURADO_APROVADO
            conta.save()
        self.message_user(request, _("Contas aprovadas para faturamento atacado."))

    @admin.action(description=_("Cancelar selecionadas"))
    def acao_cancelar(self, request, queryset):
        for conta in queryset:
            conta.status = ContaReceber.Status.CANCELADO
            conta.save()
        self.message_user(request, _("Contas canceladas."))


# ─────────────────────────────────────────────────────────────────────────────
# Caixa
# ─────────────────────────────────────────────────────────────────────────────
class CaixaMovimentacaoInline(TabularInline):
    model = CaixaMovimentacao
    extra = 1
    fields = ("tipo", "categoria", "descricao", "valor", "forma_pagamento", "operador")
    # Sem autocomplete_fields para preservar os botões nativos de pop-up.


@admin.register(CaixaDiario)
class CaixaDiarioAdmin(_FinanceiroBaseAdmin):
    list_display = (
        "data",
        "operador",
        "status",
        "saldo_inicial",
        "total_entradas",
        "total_saidas",
        "saldo_final",
    )
    list_filter = ("status",)
    date_hierarchy = "data"
    inlines = [CaixaMovimentacaoInline]
    readonly_fields = (
        "total_entradas",
        "total_saidas",
        "saldo_final",
        "created_at",
        "updated_at",
    )
    fieldsets = (
        (
            _("Caixa"),
            {"fields": ("empresa", "data", "operador", "saldo_inicial", "status")},
        ),
        (
            _("Consolidado"),
            {"fields": ("total_entradas", "total_saidas", "saldo_final")},
        ),
        (_("Observações"), {"fields": ("observacoes",)}),
        (_("Auditoria"), {"fields": ("created_at", "updated_at")}),
    )

    @admin.display(description=_("Entradas"))
    def total_entradas(self, obj):
        return obj.total_entradas if obj else 0

    @admin.display(description=_("Saídas"))
    def total_saidas(self, obj):
        return obj.total_saidas if obj else 0

    @admin.display(description=_("Saldo Final"))
    def saldo_final(self, obj):
        return obj.saldo_final if obj else 0


@admin.register(CaixaMovimentacao)
class CaixaMovimentacaoAdmin(_FinanceiroBaseAdmin):
    list_display = (
        "created_at",
        "tipo",
        "categoria",
        "descricao",
        "valor",
        "forma_pagamento",
        "operador",
    )
    list_filter = ("tipo", "forma_pagamento")
    search_fields = ("descricao", "categoria")
    # Sem autocomplete_fields para preservar os botões nativos de pop-up.
    readonly_fields = ("created_at",)
    fieldsets = (
        (
            _("Movimentação"),
            {"fields": ("empresa", "caixa", "tipo", "categoria", "descricao", "valor")},
        ),
        (
            _("Vínculos"),
            {
                "fields": (
                    "forma_pagamento",
                    "operador",
                    "conta_receber",
                    "conta_pagar",
                    "pedido",
                )
            },
        ),
        (_("Auditoria"), {"fields": ("created_at",)}),
    )
