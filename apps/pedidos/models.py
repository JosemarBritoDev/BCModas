from django.db import models
from django.utils.translation import gettext_lazy as _


class Pedido(models.Model):
    class Status(models.TextChoices):
        PENDENTE = "PENDENTE", _("Pendente")
        EM_SEPARACAO = "EM_SEPARACAO", _("Em Separação")
        FATURADO = "FATURADO", _("Faturado")
        ENVIADO = "ENVIADO", _("Enviado")
        CONCLUIDO = "CONCLUIDO", _("Concluído")

    empresa = models.ForeignKey(
        "tenants.Empresa",
        verbose_name=_("Empresa"),
        on_delete=models.CASCADE,
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
        max_length=20,
        choices=Status.choices,
        default=Status.PENDENTE,
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
        return self.quantidade * self.preco_unitario