from collections import defaultdict

from django.db.models import F

from apps.produtos.models import SKU


class EstoqueInsuficiente(Exception):
    """Levantada quando o saldo físico do SKU é menor que o solicitado."""

    def __init__(self, sku, disponivel, solicitado):
        self.sku = sku
        self.disponivel = disponivel
        self.solicitado = solicitado
        super().__init__(
            f"Estoque insuficiente para {sku}: disponível {disponivel}, "
            f"solicitado {solicitado}."
        )


def _agregar(itens):
    resumo = defaultdict(int)
    for sku_id, qtd in itens:
        resumo[int(sku_id)] += int(qtd)
    return resumo


def reservar_estoque(itens):
    """Debita o saldo físico dos SKUs de forma atômica e segura para concorrência.

    ``itens`` é um iterável de tuplas ``(sku_id, quantidade)``. Deve ser
    executada dentro de um bloco ``transaction.atomic()``. Caso algum SKU não
    tenha saldo suficiente, levanta :class:`EstoqueInsuficiente` e toda a
    transação é revertida (nenhum saldo é debitado).
    """
    resumo = _agregar(itens)
    for sku_id, qtd in resumo.items():
        if qtd <= 0:
            continue
        atualizados = SKU.objects.filter(
            pk=sku_id, quantidade_estoque__gte=qtd
        ).update(quantidade_estoque=F("quantidade_estoque") - qtd)
        if not atualizados:
            sku = SKU.objects.filter(pk=sku_id).first()
            disponivel = sku.quantidade_estoque if sku else 0
            raise EstoqueInsuficiente(sku, disponivel, qtd)
    return resumo


def repor_estoque(itens):
    """Devolve ao estoque as quantidades informadas (estorno/cancelamento)."""
    resumo = _agregar(itens)
    for sku_id, qtd in resumo.items():
        if qtd <= 0:
            continue
        SKU.objects.filter(pk=sku_id).update(
            quantidade_estoque=F("quantidade_estoque") + qtd
        )
    return resumo
