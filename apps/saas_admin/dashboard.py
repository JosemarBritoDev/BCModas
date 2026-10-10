from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone

from apps.financeiro.models import ContaPagar, ContaReceber
from apps.pedidos.models import Pedido
from apps.produtos.models import SKU

SUPERADMIN_ROLE = "SUPERADMIN"

# SKUs com saldo físico igual ou abaixo deste valor entram em alerta.
ESTOQUE_ALERTA_MINIMO = 5

# Janela de acompanhamento das contas a pagar no dashboard.
DIAS_CONTAS_A_PAGAR = 7


def _is_global(user):
    return user.is_superuser or getattr(user, "role", None) == SUPERADMIN_ROLE


def _formatar_moeda(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def dashboard_callback(request, context):
    """Callback do dashboard do Unfold: injeta os cards de KPI no contexto.

    Superadmins enxergam métricas globais. Os demais perfis enxergam apenas
    as métricas da própria empresa (isolamento por empresa).
    """
    eh_global = _is_global(request.user)

    pedidos_qs = Pedido.objects.all()
    skus_qs = SKU.objects.all()
    receber_qs = ContaReceber.objects.all()
    pagar_qs = ContaPagar.objects.all()

    if not eh_global:
        empresa_id = getattr(request.user, "empresa_id", None)
        if empresa_id:
            pedidos_qs = pedidos_qs.filter(empresa_id=empresa_id)
            skus_qs = skus_qs.filter(empresa_id=empresa_id)
            receber_qs = receber_qs.filter(empresa_id=empresa_id)
            pagar_qs = pagar_qs.filter(empresa_id=empresa_id)
        else:
            pedidos_qs = pedidos_qs.none()
            skus_qs = skus_qs.none()
            receber_qs = receber_qs.none()
            pagar_qs = pagar_qs.none()

    hoje = timezone.localdate()
    inicio_mes = hoje.replace(day=1)
    fim_mes = (inicio_mes + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    limite_pagar = hoje + timedelta(days=DIAS_CONTAS_A_PAGAR)

    pedidos_hoje_qs = pedidos_qs.filter(created_at__date=hoje)
    pedidos_do_dia = pedidos_hoje_qs.count()

    skus_alerta = skus_qs.filter(quantidade_estoque__lte=ESTOQUE_ALERTA_MINIMO).count()

    pedidos_retidos = pedidos_qs.filter(
        status_financeiro=Pedido.StatusFinanceiro.AGUARDANDO_PAGAMENTO,
        status=Pedido.Status.AGUARDANDO_PAGAMENTO,
    ).count()

    # Faturamento realizado no mês: recebidos + faturados/aprovados.
    recebido_mes = (
        receber_qs.filter(
            status=ContaReceber.Status.PAGO,
            data_recebimento__range=(inicio_mes, fim_mes),
        ).aggregate(total=Sum("valor"))["total"]
        or 0
    )
    faturado_mes = (
        receber_qs.filter(
            status=ContaReceber.Status.FATURADO_APROVADO,
            created_at__date__range=(inicio_mes, fim_mes),
        ).aggregate(total=Sum("valor"))["total"]
        or 0
    )
    faturamento_realizado = recebido_mes + faturado_mes

    a_receber_mes = (
        receber_qs.filter(
            status__in=[ContaReceber.Status.PENDENTE, ContaReceber.Status.ATRASADO],
            data_vencimento__range=(inicio_mes, fim_mes),
        ).aggregate(total=Sum("valor"))["total"]
        or 0
    )

    a_pagar_valor = (
        pagar_qs.filter(
            status__in=[ContaPagar.Status.PENDENTE, ContaPagar.Status.ATRASADO],
            data_vencimento__range=(hoje, limite_pagar),
        ).aggregate(total=Sum("valor"))["total"]
        or 0
    )
    a_pagar_qtd = pagar_qs.filter(
        status__in=[ContaPagar.Status.PENDENTE, ContaPagar.Status.ATRASADO],
        data_vencimento__range=(hoje, limite_pagar),
    ).count()

    context["kpis"] = [
        {
            "title": "Pedidos do Dia",
            "value": pedidos_do_dia,
            "description": "Pedidos registrados hoje",
            "icon": "today",
        },
        {
            "title": "Faturamento Realizado (Mês)",
            "value": _formatar_moeda(faturamento_realizado),
            "description": f"A receber no mês: {_formatar_moeda(a_receber_mes)}",
            "icon": "payments",
        },
        {
            "title": "Contas a Pagar (7 dias)",
            "value": _formatar_moeda(a_pagar_valor),
            "description": f"{a_pagar_qtd} conta(s) vencendo em breve",
            "icon": "request_quote",
        },
        {
            "title": "Pedidos Retidos",
            "value": pedidos_retidos,
            "description": "Aguardando liberação financeira",
            "icon": "lock",
        },
        {
            "title": "SKUs em Alerta de Estoque",
            "value": skus_alerta,
            "description": f"Saldo menor ou igual a {ESTOQUE_ALERTA_MINIMO} peças",
            "icon": "warning",
        },
        {
            "title": "Faturamento Total",
            "value": _formatar_moeda(
                pedidos_qs.aggregate(total=Sum("valor_total"))["total"] or 0
            ),
            "description": "Somatório histórico de pedidos",
            "icon": "trending_up",
        },
    ]

    return context
