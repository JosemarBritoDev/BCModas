"""Regras de negócio do módulo financeiro.

A sincronização entre a liquidação de uma :class:`ContaReceber` e o status
financeiro do :class:`~apps.pedidos.models.Pedido` é o ponto central da trava
de liberação: somente pedidos com pagamento confirmado podem avançar para a
produção/expedição.
"""

from datetime import timedelta

from django.utils import timezone

from apps.financeiro.models import CaixaDiario, ContaReceber
from apps.pedidos.models import Pedido

DIAS_VENCIMENTO_PADRAO = 3


def mapear_status_financeiro(conta):
    """Traduz o status da conta a receber no status financeiro do pedido."""
    if conta.status in {ContaReceber.Status.PAGO}:
        if conta.forma_pagamento == ContaReceber.FormaPagamento.FATURADO_ATACADO:
            return Pedido.StatusFinanceiro.FATURADO_ATACADO
        return Pedido.StatusFinanceiro.PAGO_LIBERADO
    if conta.status == ContaReceber.Status.FATURADO_APROVADO:
        return Pedido.StatusFinanceiro.FATURADO_ATACADO
    if conta.status == ContaReceber.Status.CANCELADO:
        return Pedido.StatusFinanceiro.CANCELADO
    return Pedido.StatusFinanceiro.AGUARDANDO_PAGAMENTO


def sincronizar_pedido_com_conta(conta):
    """Reflete a situação financeira da conta no pedido vinculado."""
    pedido = conta.pedido
    if pedido is None:
        return None

    novo = mapear_status_financeiro(conta)
    campos = []

    if pedido.status_financeiro != novo:
        pedido.status_financeiro = novo
        campos.append("status_financeiro")

    liberado = novo in {
        Pedido.StatusFinanceiro.PAGO_LIBERADO,
        Pedido.StatusFinanceiro.FATURADO_ATACADO,
    }

    if liberado and pedido.status == Pedido.Status.AGUARDANDO_PAGAMENTO:
        pedido.status = Pedido.Status.PAGO_LIBERADO
        campos.append("status")
    elif (
        not liberado
        and novo == Pedido.StatusFinanceiro.AGUARDANDO_PAGAMENTO
        and pedido.status == Pedido.Status.PAGO_LIBERADO
    ):
        pedido.status = Pedido.Status.AGUARDANDO_PAGAMENTO
        campos.append("status")

    if campos:
        pedido.save(update_fields=campos)
    return pedido


def criar_conta_receber_para_pedido(pedido, vencimento=None, forma_pagamento=""):
    """Cria (uma única vez) a conta a receber vinculada a um novo pedido."""
    if pedido is None or not pedido.pk:
        return None
    vencimento = vencimento or (timezone.localdate() + timedelta(days=DIAS_VENCIMENTO_PADRAO))
    conta, _ = ContaReceber.objects.get_or_create(
        pedido=pedido,
        defaults={
            "empresa": pedido.empresa,
            "cliente": pedido.cliente,
            "cliente_nome": pedido.cliente_nome,
            "origem": ContaReceber.Origem.PEDIDO,
            "descricao": f"Recebimento do pedido #{pedido.pk}",
            "valor": pedido.valor_total,
            "data_vencimento": vencimento,
            "status": ContaReceber.Status.PENDENTE,
            "forma_pagamento": forma_pagamento,
        },
    )
    return conta


def obter_caixa_do_dia(empresa, data=None):
    """Retorna (ou abre) o caixa do dia para a empresa informada."""
    data = data or timezone.localdate()
    caixa, _ = CaixaDiario.objects.get_or_create(
        empresa=empresa,
        data=data,
        defaults={"saldo_inicial": 0},
    )
    return caixa


def _registrar_movimento(conta, tipo, caixa, operador=None):
    """Cria a movimentação de caixa correspondente a uma liquidação."""
    from apps.financeiro.models import CaixaMovimentacao

    filtros = {f"conta_{'receber' if tipo == CaixaMovimentacao.Tipo.ENTRADA else 'pagar'}": conta}
    existente = CaixaMovimentacao.objects.filter(**filtros).first()
    if existente:
        return existente
    return CaixaMovimentacao.objects.create(
        empresa=conta.empresa,
        caixa=caixa,
        tipo=tipo,
        categoria="Recebimento" if tipo == CaixaMovimentacao.Tipo.ENTRADA else "Pagamento",
        descricao=conta.descricao or str(conta),
        valor=conta.valor,
        forma_pagamento=getattr(conta, "forma_pagamento", "") or "",
        operador=operador,
        **filtros,
    )


def registrar_recebimento(conta, data_recebimento=None, forma_pagamento=None, operador=None):
    """Marca uma conta a receber como paga e lança a entrada no caixa."""
    from apps.financeiro.models import CaixaMovimentacao

    conta.data_recebimento = data_recebimento or timezone.localdate()
    if forma_pagamento:
        conta.forma_pagamento = forma_pagamento
    conta.status = ContaReceber.Status.PAGO
    conta.save()
    caixa = obter_caixa_do_dia(conta.empresa, conta.data_recebimento)
    _registrar_movimento(conta, CaixaMovimentacao.Tipo.ENTRADA, caixa, operador)
    return conta


def registrar_pagamento(conta, data_pagamento=None, operador=None):
    """Marca uma conta a pagar como paga e lança a saída no caixa."""
    from apps.financeiro.models import CaixaMovimentacao, ContaPagar

    conta.data_pagamento = data_pagamento or timezone.localdate()
    conta.status = ContaPagar.Status.PAGO
    conta.save()
    caixa = obter_caixa_do_dia(conta.empresa, conta.data_pagamento)
    _registrar_movimento(conta, CaixaMovimentacao.Tipo.SAIDA, caixa, operador)
    return conta

