from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _


class Pedido(models.Model):
    class Status(models.TextChoices):
        # Fluxo financeiro / inicial
        AGUARDANDO_PAGAMENTO = "AGUARDANDO_PAGAMENTO", _("Aguardando Pagamento")
        PAGO_LIBERADO = "PAGO_LIBERADO", _("Pago / Liberado")
        # Fluxo operacional (exige liberação financeira)
        EM_PRODUCAO = "EM_PRODUCAO", _("Em Produção")
        EM_SEPARACAO = "EM_SEPARACAO", _("Em Separação")
        PRONTO_ENTREGA = "PRONTO_ENTREGA", _("Pronto p/ Entrega")
        ENVIADO = "ENVIADO", _("Enviado")
        ENTREGUE = "ENTREGUE", _("Entregue")
        CONCLUIDO = "CONCLUIDO", _("Concluído")
        CANCELADO = "CANCELADO", _("Cancelado")

    class StatusFinanceiro(models.TextChoices):
        AGUARDANDO_PAGAMENTO = "AGUARDANDO_PAGAMENTO", _("Aguardando Pagamento")
        PAGO_LIBERADO = "PAGO_LIBERADO", _("Pago / Liberado")
        FATURADO_ATACADO = "FATURADO_ATACADO", _("Faturado Atacado")
        CANCELADO = "CANCELADO", _("Cancelado")

    class FormaPagamento(models.TextChoices):
        PIX = "PIX", _("Pix")
        CREDITO = "CREDITO", _("Cartão de Crédito")
        DEBITO = "DEBITO", _("Cartão de Débito")

    class TipoEntrega(models.TextChoices):
        RETIRADA_LOCAL = "RETIRADA_LOCAL", _("Retirar no Local (Grátis)")
        ENTREGA = "ENTREGA", _("Entrega a Combinar")

    # Etapas operacionais que só podem ser atingidas com a liberação financeira.
    STATUS_BLOQUEADOS_FINANCEIRO = {
        "EM_PRODUCAO",
        "EM_SEPARACAO",
        "PRONTO_ENTREGA",
        "ENVIADO",
        "ENTREGUE",
        "CONCLUIDO",
    }
    STATUS_FINANCEIROS_LIBERADOS = {"PAGO_LIBERADO", "FATURADO_ATACADO"}

    empresa = models.ForeignKey(
        "tenants.Empresa",
        verbose_name=_("Empresa"),
        on_delete=models.CASCADE,
        related_name="pedidos",
    )
    cliente = models.ForeignKey(
        "clientes.Cliente",
        verbose_name=_("Cliente"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pedidos",
    )
    cliente_nome = models.CharField(_("Nome do Cliente"), max_length=150)
    cliente_documento = models.CharField(
        _("Documento do Cliente"), max_length=20, blank=True, default=""
    )
    cliente_whatsapp = models.CharField(_("WhatsApp do Cliente"), max_length=20)
    total_itens = models.PositiveIntegerField(_("Total de Itens"), default=0)
    valor_total = models.DecimalField(
        _("Valor Total"), max_digits=12, decimal_places=2, default=0
    )
    status = models.CharField(
        _("Status"),
        max_length=30,
        choices=Status.choices,
        default=Status.AGUARDANDO_PAGAMENTO,
    )
    status_financeiro = models.CharField(
        _("Status Financeiro"),
        max_length=30,
        choices=StatusFinanceiro.choices,
        default=StatusFinanceiro.AGUARDANDO_PAGAMENTO,
    )
    forma_pagamento = models.CharField(
        _("Forma de Pagamento"),
        max_length=20,
        choices=FormaPagamento.choices,
        default=FormaPagamento.PIX,
    )
    tipo_entrega = models.CharField(
        _("Tipo de Entrega"),
        max_length=20,
        choices=TipoEntrega.choices,
        default=TipoEntrega.RETIRADA_LOCAL,
    )
    endereco_entrega = models.TextField(_("Endereço de Entrega"), blank=True, default="")
    taxa_entrega = models.DecimalField(
        _("Taxa de Entrega"), max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    aceite_lgpd = models.BooleanField(_("Aceite LGPD"), default=False)
    ip_aceite = models.GenericIPAddressField(
        _("IP do Aceite"), blank=True, null=True
    )
    data_aceite = models.DateTimeField(_("Data do Aceite"), blank=True, null=True)
    versao_termos = models.CharField(
        _("Versão dos Termos"), max_length=20, blank=True, default=""
    )
    created_at = models.DateTimeField(_("Criado em"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Atualizado em"), auto_now=True)

    class Meta:
        verbose_name = _("Pedido")
        verbose_name_plural = _("Pedidos")
        ordering = ["-created_at"]

    def __str__(self):
        return f"Pedido #{self.pk} - {self.cliente_nome}"

    @property
    def liberado_financeiramente(self):
        return self.status_financeiro in self.STATUS_FINANCEIROS_LIBERADOS

    @property
    def aguardando_liberacao_financeira(self):
        return self.status_financeiro == self.StatusFinanceiro.AGUARDANDO_PAGAMENTO

    @property
    def valor_total_com_frete(self):
        """Total geral do pedido (produtos + taxa de entrega, quando houver)."""
        return (self.valor_total or Decimal("0.00")) + (self.taxa_entrega or Decimal("0.00"))

    def clean(self):
        """Impede avanço operacional sem confirmação do pagamento.

        Se houver uma Conta a Receber vinculada, considera-se liberado quando
        ela estiver PAGA ou FATURADA/APROVADA.
        """
        liberado = self.liberado_financeiramente
        if not liberado and self.pk:
            conta_liberada = self.contas_receber.filter(
                status__in=[
                    "PAGO",
                    "FATURADO_APROVADO",
                ]
            ).exists()
            liberado = conta_liberada

        if self.status in self.STATUS_BLOQUEADOS_FINANCEIRO and not liberado:
            raise ValidationError(
                {
                    "status": _(
                        "Pedido bloqueado financeiramente. Confirme o pagamento "
                        "(Conta a Receber paga ou faturada) antes de avançar para "
                        "produção, separação, entrega ou conclusão."
                    )
                }
            )


class ItemPedido(models.Model):
    pedido = models.ForeignKey(
        Pedido,
        verbose_name=_("Pedido"),
        on_delete=models.CASCADE,
        related_name="itens",
    )
    sku = models.ForeignKey(
        "produtos.SKU",
        verbose_name=_("SKU"),
        on_delete=models.PROTECT,
        related_name="itens_pedido",
    )
    quantidade = models.PositiveIntegerField(_("Quantidade"), default=1)
    preco_unitario = models.DecimalField(
        _("Preço Unitário"), max_digits=10, decimal_places=2
    )

    class Meta:
        verbose_name = _("Item do Pedido")
        verbose_name_plural = _("Itens do Pedido")
        ordering = ["pk"]

    def __str__(self):
        return f"{self.quantidade}x {self.sku}"

    @property
    def subtotal(self):
        if self.quantidade is None or self.preco_unitario is None:
            return Decimal("0.00")
        return self.quantidade * self.preco_unitario