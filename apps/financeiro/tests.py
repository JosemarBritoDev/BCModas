from datetime import timedelta
from decimal import Decimal

from django.contrib.admin.sites import AdminSite
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.financeiro.admin import ContaPagarAdmin, ContaReceberAdmin
from apps.financeiro.models import CaixaMovimentacao, ContaPagar, ContaReceber
from apps.financeiro.services import (
    criar_conta_receber_para_pedido,
    registrar_recebimento,
)
from apps.pedidos.models import Pedido
from apps.produtos.models import Modelo
from apps.tenants.models import Empresa
from apps.usuarios.models import Usuario


def criar_empresa(**extra):
    dados = {
        "nome_fantasia": "Fábrica Financeira",
        "cnpj": "22.222.222/0001-22",
        "status": Empresa.Status.ATIVO,
    }
    dados.update(extra)
    return Empresa.objects.create(**dados)


class TravaFinanceiraTests(TestCase):
    def setUp(self):
        self.empresa = criar_empresa()

    def _pedido(self, **extra):
        dados = {
            "empresa": self.empresa,
            "cliente_nome": "Lojista",
            "cliente_whatsapp": "11999999999",
            "valor_total": Decimal("100.00"),
        }
        dados.update(extra)
        return Pedido.objects.create(**dados)

    def test_pedido_nasce_aguardando_pagamento(self):
        pedido = self._pedido()
        self.assertEqual(pedido.status, Pedido.Status.AGUARDANDO_PAGAMENTO)
        self.assertEqual(
            pedido.status_financeiro, Pedido.StatusFinanceiro.AGUARDANDO_PAGAMENTO
        )
        self.assertTrue(pedido.aguardando_liberacao_financeira)

    def test_avancar_sem_pagamento_e_bloqueado(self):
        pedido = self._pedido(status=Pedido.Status.EM_PRODUCAO)
        with self.assertRaises(ValidationError):
            pedido.full_clean()

    def test_avancar_com_pagamento_liberado(self):
        pedido = self._pedido(
            status=Pedido.Status.EM_PRODUCAO,
            status_financeiro=Pedido.StatusFinanceiro.PAGO_LIBERADO,
        )
        pedido.full_clean()

    def test_conta_receber_paga_libera_pedido(self):
        pedido = self._pedido()
        conta = criar_conta_receber_para_pedido(pedido)
        self.assertIsNotNone(conta)
        registrar_recebimento(conta)
        pedido.refresh_from_db()
        conta.refresh_from_db()
        self.assertEqual(conta.status, ContaReceber.Status.PAGO)
        self.assertEqual(
            pedido.status_financeiro, Pedido.StatusFinanceiro.PAGO_LIBERADO
        )
        self.assertEqual(pedido.status, Pedido.Status.PAGO_LIBERADO)

    def test_faturamento_atacado_libera(self):
        pedido = self._pedido()
        conta = criar_conta_receber_para_pedido(pedido)
        conta.status = ContaReceber.Status.FATURADO_APROVADO
        conta.save()
        pedido.refresh_from_db()
        self.assertEqual(
            pedido.status_financeiro, Pedido.StatusFinanceiro.FATURADO_ATACADO
        )
        pedido.status = Pedido.Status.EM_SEPARACAO
        pedido.full_clean()

    def test_cancelamento_reverte_liberacao(self):
        pedido = self._pedido()
        conta = criar_conta_receber_para_pedido(pedido)
        registrar_recebimento(conta)
        conta.status = ContaReceber.Status.CANCELADO
        conta.save()
        pedido.refresh_from_db()
        self.assertEqual(
            pedido.status_financeiro, Pedido.StatusFinanceiro.CANCELADO
        )

    def test_criar_conta_receber_e_idempotente(self):
        pedido = self._pedido()
        criar_conta_receber_para_pedido(pedido)
        criar_conta_receber_para_pedido(pedido)
        self.assertEqual(pedido.contas_receber.count(), 1)

    def test_recebimento_gera_entrada_no_caixa(self):
        pedido = self._pedido()
        conta = criar_conta_receber_para_pedido(pedido)
        registrar_recebimento(conta)
        movimento = CaixaMovimentacao.objects.get(conta_receber=conta)
        self.assertEqual(movimento.tipo, CaixaMovimentacao.Tipo.ENTRADA)
        self.assertEqual(movimento.valor, Decimal("100.00"))


class ContaAtrasoTests(TestCase):
    def setUp(self):
        self.empresa = criar_empresa(cnpj="33.333.333/0001-33")

    def test_conta_a_pagar_vencida_fica_atrasada(self):
        conta = ContaPagar.objects.create(
            empresa=self.empresa,
            fornecedor="Fornecedor",
            categoria=ContaPagar.Categoria.MATERIA_PRIMA,
            descricao="Malha",
            valor=Decimal("100.00"),
            data_vencimento=timezone.localdate() - timedelta(days=3),
        )
        self.assertEqual(conta.status, ContaPagar.Status.ATRASADO)
        self.assertTrue(conta.esta_atrasada)

    def test_conta_a_receber_vencida_fica_atrasada(self):
        conta = ContaReceber.objects.create(
            empresa=self.empresa,
            cliente_nome="Cliente",
            valor=Decimal("50.00"),
            data_vencimento=timezone.localdate() - timedelta(days=1),
        )
        self.assertEqual(conta.status, ContaReceber.Status.ATRASADO)


class FinanceiroRbacTests(TestCase):
    def setUp(self):
        self.empresa = criar_empresa(cnpj="44.444.444/0001-44")
        self.financeiro = Usuario.objects.create_user(
            username="fin",
            password="SenhaForte123",
            role=Usuario.Role.FINANCEIRO,
            empresa=self.empresa,
            is_staff=True,
        )
        self.vendedor = Usuario.objects.create_user(
            username="vend",
            password="SenhaForte123",
            role=Usuario.Role.VENDAS,
            empresa=self.empresa,
            is_staff=True,
        )
        self.gerente = Usuario.objects.create_user(
            username="ger",
            password="SenhaForte123",
            role=Usuario.Role.GERENTE,
            empresa=self.empresa,
            is_staff=True,
        )

    def _request(self, user, path="/admin/"):
        request = RequestFactory().get(path)
        request.user = user
        return request

    def test_financeiro_acessa_contas(self):
        admin_receber = ContaReceberAdmin(ContaReceber, AdminSite())
        admin_pagar = ContaPagarAdmin(ContaPagar, AdminSite())
        req = self._request(self.financeiro)
        self.assertTrue(admin_receber.has_module_permission(req))
        self.assertTrue(admin_receber.has_change_permission(req))
        self.assertTrue(admin_pagar.has_module_permission(req))

    def test_vendedor_nao_acessa_financeiro(self):
        admin_receber = ContaReceberAdmin(ContaReceber, AdminSite())
        self.assertFalse(
            admin_receber.has_module_permission(self._request(self.vendedor))
        )
        self.assertFalse(
            admin_receber.has_view_permission(self._request(self.vendedor))
        )

    def test_financeiro_nao_acessa_produtos(self):
        from apps.produtos.admin import SKUAdmin
        from apps.produtos.models import SKU

        admin_sku = SKUAdmin(SKU, AdminSite())
        self.assertFalse(
            admin_sku.has_module_permission(self._request(self.financeiro))
        )

    def test_navegacao_financeiro_mostra_apenas_financeiro(self):
        from core.settings import bc_modas_navigation

        request = self._request(self.financeiro)
        titulos = [bloco["title"] for bloco in bc_modas_navigation(request)]
        self.assertEqual(titulos, ["Financeiro"])

    def test_navegacao_gerente_mostra_tudo(self):
        from core.settings import bc_modas_navigation

        request = self._request(self.gerente)
        titulos = [bloco["title"] for bloco in bc_modas_navigation(request)]
        self.assertIn("Financeiro", titulos)
        self.assertIn("Sistema", titulos)
        self.assertIn("Vendas", titulos)

    def test_dashboard_renderiza_com_kpis(self):
        self.client.force_login(self.gerente)
        resp = self.client.get(reverse("admin:index"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("kpis", resp.context)
