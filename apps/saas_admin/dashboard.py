from django.db.models import Sum

from apps.pedidos.models import Pedido
from apps.produtos.models import Modelo
from apps.tenants.models import Empresa

SUPERADMIN_ROLE = "SUPERADMIN"


def _is_global(user):
    return user.is_superuser or getattr(user, "role", None) == SUPERADMIN_ROLE


def dashboard_callback(request, context):
    """Callback do dashboard do Unfold: injeta os cards de KPI no contexto.

    Superadmins enxergam métricas globais do SaaS. Os demais perfis enxergam
    apenas as métricas da própria empresa (isolamento multi-tenant).
    """
    eh_global = _is_global(request.user)

    pedidos_qs = Pedido.objects.all()
    modelos_qs = Modelo.objects.all()
    empresas_qs = Empresa.objects.all()

    if not eh_global:
        empresa_id = getattr(request.user, "empresa_id", None)
        if empresa_id:
            pedidos_qs = pedidos_qs.filter(empresa_id=empresa_id)
            modelos_qs = modelos_qs.filter(empresa_id=empresa_id)
            empresas_qs = empresas_qs.filter(pk=empresa_id)
        else:
            pedidos_qs = pedidos_qs.none()
            modelos_qs = modelos_qs.none()
            empresas_qs = empresas_qs.none()

    total_pedidos = pedidos_qs.count()
    faturamento = pedidos_qs.aggregate(total=Sum("valor_total"))["total"] or 0
    total_modelos = modelos_qs.count()
    empresas_ativas = empresas_qs.filter(status=Empresa.Status.ATIVO).count()

    context["kpis"] = [
        {
            "title": "Pedidos",
            "value": total_pedidos,
            "description": "Total de pedidos registrados",
            "icon": "shopping_cart",
        },
        {
            "title": "Faturamento",
            "value": f"R$ {faturamento:,.2f}",
            "description": "Acumulado em pedidos",
            "icon": "payments",
        },
        {
            "title": "Modelos",
            "value": total_modelos,
            "description": "Modelos no catálogo",
            "icon": "checkroom",
        },
        {
            "title": "Empresas Ativas",
            "value": empresas_ativas,
            "description": "Confecções com assinatura ativa",
            "icon": "apartment",
        },
    ]

    return context