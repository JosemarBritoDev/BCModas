from django.db.models import Sum
from django.utils import timezone

from apps.pedidos.models import Pedido
from apps.produtos.models import SKU

SUPERADMIN_ROLE = "SUPERADMIN"

# SKUs com saldo físico igual ou abaixo deste valor entram em alerta.
ESTOQUE_ALERTA_MINIMO = 5


def _is_global(user):
    return user.is_superuser or getattr(user, "role", None) == SUPERADMIN_ROLE


def dashboard_callback(request, context):
    """Callback do dashboard do Unfold: injeta os cards de KPI no contexto.

    Superadmins enxergam métricas globais. Os demais perfis enxergam apenas
    as métricas da própria empresa (isolamento por empresa).
    """
    eh_global = _is_global(request.user)

    pedidos_qs = Pedido.objects.all()
    skus_qs = SKU.objects.all()

    if not eh_global:
        empresa_id = getattr(request.user, "empresa_id", None)
        if empresa_id:
            pedidos_qs = pedidos_qs.filter(empresa_id=empresa_id)
            skus_qs = skus_qs.filter(empresa_id=empresa_id)
        else:
            pedidos_qs = pedidos_qs.none()
            skus_qs = skus_qs.none()

    hoje = timezone.localdate()
    pedidos_hoje_qs = pedidos_qs.filter(created_at__date=hoje)

    pedidos_do_dia = pedidos_hoje_qs.count()
    faturamento = pedidos_qs.aggregate(total=Sum("valor_total"))["total"] or 0
    faturamento_hoje = (
        pedidos_hoje_qs.aggregate(total=Sum("valor_total"))["total"] or 0
    )
    skus_alerta = skus_qs.filter(quantidade_estoque__lte=ESTOQUE_ALERTA_MINIMO).count()
    pedidos_pendentes = pedidos_qs.filter(status=Pedido.Status.PENDENTE).count()

    context["kpis"] = [
        {
            "title": "Pedidos do Dia",
            "value": pedidos_do_dia,
            "description": "Pedidos registrados hoje",
            "icon": "today",
        },
        {
            "title": "Faturamento",
            "value": f"R$ {faturamento:,.2f}",
            "description": f"Hoje: R$ {faturamento_hoje:,.2f}",
            "icon": "payments",
        },
        {
            "title": "SKUs em Alerta de Estoque",
            "value": skus_alerta,
            "description": f"Saldo menor ou igual a {ESTOQUE_ALERTA_MINIMO} peças",
            "icon": "warning",
        },
        {
            "title": "Pedidos Pendentes",
            "value": pedidos_pendentes,
            "description": "Aguardando separação/faturamento",
            "icon": "pending_actions",
        },
    ]

    return context
