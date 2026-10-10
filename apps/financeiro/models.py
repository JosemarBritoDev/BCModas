from decimal import Decimal

from django.db import models
from django.db.models import Sum
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class ContaPagar(models.Model):
    """Despesa da fábrica (matéria-prima, folha, operacional, impostos)."""

    class Categoria(models.TextChoices):
        MATERIA_PRIMA = "MATERIA_PRIMA", _("Matéria-Prima")
        FOLHA_PAGAMENTO = "FOLHA_PAGAMENTO", _("Folha de Pagamento")
        OPERACIONAL = "OPERACIONAL", _("Operacional")
        IMPOSTOS = "IMPOSTOS", _("Impostos")
        OUTROS = "OUTROS", _("Outros")

    class Status(models.TextChoices):
        PENDENTE = "PENDENTE", _("Pendente")
        PAGO = "PAGO", _("Pago")
        ATRASADO = "ATRASADO", _("Atrasado")
        CANCELADO = "CANCELADO", _("Cancelado")

    empresa = models.ForeignKey(
        "tenants.Empresa",
        verbose_name=_("Empresa"),
        on_delete=models.CASCADE,
        related_name="contas_pagar",
    )
    fornecedor = models.CharField(_("Fornecedor / Credor"), max_length=150)
    categoria = models.CharField(
        _("Categoria"),
        max_length=20,
        choices=Categoria.choices,
        default=Categoria.OPERACIONAL,
    )
    descricao = models.CharField(_("Descrição"), max_length=255)
    valor = models.DecimalField(_("Valor"), max_digits=12, decimal_places=2)
    data_vencimento = models.DateField(_("Data de Vencimento"))
    data_pagamento = models.DateField(_("Data de Pagamento"), blank=True, null=True)
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDENTE,
    )
    comprovante = models.FileField(
        _("Comprovante"),
        upload_to="financeiro/comprovantes/",
        blank=True,
        null=True,
    )
    observacoes = models.TextField(_("Observações"), blank=True, default="")
    created_at = models.DateTimeField(_("Criado em"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Atualizado em"), auto_now=True)

    class Meta:
        verbose_name = _("Conta a Pagar")
        verbose_name_plural = _("Contas a Pagar")
        ordering = ["data_vencimento", "pk"]

    def __str__(self):
        return f"{self.fornecedor} - R$ {self.valor}"

    @property
    def esta_atrasada(self):
        return bool(
            self.status in {self.Status.PENDENTE, self.Status.ATRASADO}
            and self.data_vencimento
            and self.data_vencimento < timezone.localdate()
        )

    def save(self, *args, **kwargs):
        if (
            self.status == self.Status.PENDENTE
            and self.data_vencimento
            and self.data_vencimento < timezone.localdate()
        ):
            self.status = self.Status.ATRASADO
        super().save(*args, **kwargs)


class ContaReceber(models.Model):
    """Faturamento/recebimento vinculado a um pedido ou de origem externa."""

    class Origem(models.TextChoices):
        PEDIDO = "PEDIDO", _("Pedido")
        EXTERNA = "EXTERNA", _("Origem Externa")

    class FormaPagamento(models.TextChoices):
        PIX = "PIX", _("Pix")
        CARTAO = "CARTAO", _("Cartão")
        BOLETO = "BOLETO", _("Boleto")
        DINHEIRO = "DINHEIRO", _("Dinheiro")
        FATURADO_ATACADO = "FATURADO_ATACADO", _("Faturado Atacado")

    class Status(models.TextChoices):
        PENDENTE = "PENDENTE", _("Pendente")
        PAGO = "PAGO", _("Recebido")
        FATURADO_APROVADO = "FATURADO_APROVADO", _("Faturado / Aprovado")
        ATRASADO = "ATRASADO", _("Atrasado")
        CANCELADO = "CANCELADO", _("Cancelado")

    STATUS_LIBERADOS = {Status.PAGO, Status.FATURADO_APROVADO}

    empresa = models.ForeignKey(
        "tenants.Empresa",
        verbose_name=_("Empresa"),
        on_delete=models.CASCADE,
        related_name="contas_receber",
    )
    pedido = models.ForeignKey(
        "pedidos.Pedido",
        verbose_name=_("Pedido"),
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="contas_receber",
    )
    cliente = models.ForeignKey(
        "clientes.Cliente",
        verbose_name=_("Cliente"),
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="contas_receber",
    )
    cliente_nome = models.CharField(
        _("Nome do Cliente / Origem"), max_length=180, blank=True, default=""
    )
    origem = models.CharField(
        _("Origem"),
        max_length=10,
        choices=Origem.choices,
        default=Origem.PEDIDO,
    )
    descricao = models.CharField(_("Descrição"), max_length=255, blank=True, default="")
    forma_pagamento = models.CharField(
        _("Forma de Pagamento"),
        max_length=20,
        choices=FormaPagamento.choices,
        blank=True,
        default="",
    )
    valor = models.DecimalField(_("Valor"), max_digits=12, decimal_places=2)
    data_vencimento = models.DateField(_("Data de Vencimento"))
    data_recebimento = models.DateField(_("Data de Recebimento"), blank=True, null=True)
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDENTE,
    )
    comprovante = models.FileField(
        _("Comprovante"),
        upload_to="financeiro/comprovantes/",
        blank=True,
        null=True,
    )
    observacoes = models.TextField(_("Observações"), blank=True, default="")
    created_at = models.DateTimeField(_("Criado em"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Atualizado em"), auto_now=True)

    class Meta:
        verbose_name = _("Conta a Receber")
        verbose_name_plural = _("Contas a Receber")
        ordering = ["data_vencimento", "pk"]

    def __str__(self):
        return f"#{self.pk} {self.cliente_nome or 'Recebimento'} - R$ {self.valor}"

    @property
    def esta_atrasada(self):
        return bool(
            self.status in {self.Status.PENDENTE, self.Status.ATRASADO}
            and self.data_vencimento
            and self.data_vencimento < timezone.localdate()
        )

    @property
    def libera_pedido(self):
        return self.status in self.STATUS_LIBERADOS

    def save(self, *args, **kwargs):
        status_anterior = None
        if self.pk:
            status_anterior = (
                type(self)
                .objects.filter(pk=self.pk)
                .values_list("status", flat=True)
                .first()
            )

        if (
            self.status == self.Status.PENDENTE
            and self.data_vencimento
            and self.data_vencimento < timezone.localdate()
        ):
            self.status = self.Status.ATRASADO

        super().save(*args, **kwargs)

        if self.pedido_id and self.status != status_anterior:
            from apps.financeiro.services import sincronizar_pedido_com_conta

            sincronizar_pedido_com_conta(self)


class CaixaDiario(models.Model):
    """Caixa físico do dia: consolida entradas e saídas de recursos."""

    class Status(models.TextChoices):
        ABERTO = "ABERTO", _("Aberto")
        FECHADO = "FECHADO", _("Fechado")

    empresa = models.ForeignKey(
        "tenants.Empresa",
        verbose_name=_("Empresa"),
        on_delete=models.CASCADE,
        related_name="caixas_diarios",
    )
    data = models.DateField(_("Data"), default=timezone.localdate)
    saldo_inicial = models.DecimalField(
        _("Saldo Inicial"), max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    operador = models.ForeignKey(
        "usuarios.Usuario",
        verbose_name=_("Operador"),
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="caixas_abertos",
    )
    status = models.CharField(
        _("Status"),
        max_length=10,
        choices=Status.choices,
        default=Status.ABERTO,
    )
    observacoes = models.TextField(_("Observações"), blank=True, default="")
    created_at = models.DateTimeField(_("Criado em"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Atualizado em"), auto_now=True)

    class Meta:
        verbose_name = _("Caixa Diário")
        verbose_name_plural = _("Caixas Diários")
        ordering = ["-data", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["empresa", "data"], name="caixa_diario_unico_por_empresa_dia"
            )
        ]

    def __str__(self):
        return f"Caixa {self.data:%d/%m/%Y}"

    def _somar(self, tipo):
        total = self.movimentacoes.filter(tipo=tipo).aggregate(
            total=Sum("valor")
        )["total"]
        return total or Decimal("0.00")

    @property
    def total_entradas(self):
        return self._somar(CaixaMovimentacao.Tipo.ENTRADA)

    @property
    def total_saidas(self):
        return self._somar(CaixaMovimentacao.Tipo.SAIDA)

    @property
    def saldo_final(self):
        return (self.saldo_inicial or Decimal("0.00")) + self.total_entradas - self.total_saidas

    @property
    def saldo_atual(self):
        return self.saldo_final


class CaixaMovimentacao(models.Model):
    """Lançamento de entrada ou saída do caixa (histórico com operador)."""

    class Tipo(models.TextChoices):
        ENTRADA = "ENTRADA", _("Entrada")
        SAIDA = "SAIDA", _("Saída")

    empresa = models.ForeignKey(
        "tenants.Empresa",
        verbose_name=_("Empresa"),
        on_delete=models.CASCADE,
        related_name="caixa_movimentacoes",
    )
    caixa = models.ForeignKey(
        CaixaDiario,
        verbose_name=_("Caixa Diário"),
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="movimentacoes",
    )
    tipo = models.CharField(_("Tipo"), max_length=10, choices=Tipo.choices)
    categoria = models.CharField(_("Categoria"), max_length=80, blank=True, default="")
    descricao = models.CharField(_("Descrição"), max_length=255)
    valor = models.DecimalField(_("Valor"), max_digits=12, decimal_places=2)
    forma_pagamento = models.CharField(
        _("Forma de Pagamento"),
        max_length=20,
        choices=ContaReceber.FormaPagamento.choices,
        blank=True,
        default="",
    )
    conta_receber = models.ForeignKey(
        ContaReceber,
        verbose_name=_("Conta a Receber"),
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="movimentacoes",
    )
    conta_pagar = models.ForeignKey(
        ContaPagar,
        verbose_name=_("Conta a Pagar"),
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="movimentacoes",
    )
    pedido = models.ForeignKey(
        "pedidos.Pedido",
        verbose_name=_("Pedido"),
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="movimentacoes_caixa",
    )
    operador = models.ForeignKey(
        "usuarios.Usuario",
        verbose_name=_("Operador"),
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="movimentacoes_caixa",
    )
    created_at = models.DateTimeField(_("Criado em"), auto_now_add=True)

    class Meta:
        verbose_name = _("Movimentação de Caixa")
        verbose_name_plural = _("Movimentações de Caixa")
        ordering = ["-created_at", "-pk"]

    def save(self, *args, **kwargs):
        if self.empresa_id is None and self.caixa_id:
            self.empresa = self.caixa.empresa
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_tipo_display()} - R$ {self.valor}"
