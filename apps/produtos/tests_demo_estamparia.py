from django.core.management import call_command
from django.test import TestCase

from apps.clientes.models import Cliente
from apps.financeiro.models import CaixaMovimentacao, ContaPagar, ContaReceber
from apps.pedidos.models import ItemPedido, Pedido
from apps.produtos.models import Categoria, Modelo, SKU
from apps.tenants.models import Empresa


class PopularDemoEstampariaTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            nome_fantasia="Confecção Demo",
            cnpj="11.111.111/0001-11",
            email="demo@estamparia.com.br",
            whatsapp_comercial="(11) 99999-0000",
        )

    def _contagens(self):
        return {
            "categorias": Categoria.objects.filter(empresa=self.empresa).count(),
            "modelos": Modelo.objects.filter(empresa=self.empresa).count(),
            "skus": SKU.objects.filter(empresa=self.empresa).count(),
            "clientes": Cliente.objects.filter(empresa=self.empresa).count(),
            "pedidos": Pedido.objects.filter(
                empresa=self.empresa, versao_termos__startswith="demo-estamparia"
            ).count(),
            "itens": ItemPedido.objects.filter(pedido__empresa=self.empresa).count(),
            "a_receber": ContaReceber.objects.filter(empresa=self.empresa).count(),
            "a_pagar": ContaPagar.objects.filter(empresa=self.empresa).count(),
            "caixa": CaixaMovimentacao.objects.filter(empresa=self.empresa).count(),
        }

    def test_popula_e_e_idempotente(self):
        call_command("popular_demo_estamparia")
        contagens = self._contagens()

        self.assertEqual(contagens["categorias"], 7)
        self.assertEqual(contagens["modelos"], 20)
        self.assertGreaterEqual(contagens["skus"], 40)
        self.assertEqual(contagens["clientes"], 6)
        self.assertGreaterEqual(contagens["pedidos"], 5)
        self.assertLessEqual(contagens["pedidos"], 8)
        self.assertGreater(contagens["itens"], 0)
        self.assertGreater(contagens["a_receber"], 0)
        self.assertGreater(contagens["a_pagar"], 0)
        self.assertGreater(contagens["caixa"], 0)

        # Segunda execução não deve duplicar nada.
        call_command("popular_demo_estamparia")
        self.assertEqual(contagens, self._contagens())

    def test_grade_de_skus_entre_2_e_3_por_modelo(self):
        call_command("popular_demo_estamparia")
        for modelo in Modelo.objects.filter(empresa=self.empresa):
            total = modelo.skus.count()
            self.assertGreaterEqual(total, 2, modelo.nome)
            self.assertLessEqual(total, 3, modelo.nome)
            # Cada SKU tem cor hexadecimal válida e estoque definido.
            for sku in modelo.skus.all():
                self.assertTrue(sku.cor_hex.startswith("#"))
                self.assertEqual(len(sku.cor_hex), 7)

    def test_clientes_pf_e_pj_com_documentos(self):
        call_command("popular_demo_estamparia")
        tipos = set(Cliente.objects.values_list("tipo_pessoa", flat=True))
        self.assertEqual(tipos, {"PF", "PJ"})
        for cliente in Cliente.objects.all():
            self.assertTrue(cliente.cpf_cnpj)
            if cliente.tipo_pessoa == "PJ":
                self.assertEqual(len(cliente.cpf_cnpj), 18)
            else:
                self.assertEqual(len(cliente.cpf_cnpj), 14)

    def test_status_dos_pedidos_e_liberacao_financeira(self):
        call_command("popular_demo_estamparia")
        status = set(
            Pedido.objects.filter(
                empresa=self.empresa, versao_termos__startswith="demo-estamparia"
            ).values_list("status", flat=True)
        )
        self.assertIn(Pedido.Status.AGUARDANDO_PAGAMENTO, status)
        self.assertIn(Pedido.Status.EM_PRODUCAO, status)
        self.assertIn(Pedido.Status.ENTREGUE, status)

        # Pedidos operacionais precisam estar liberados financeiramente.
        operacionais = Pedido.objects.filter(
            empresa=self.empresa,
            status__in=Pedido.STATUS_BLOQUEADOS_FINANCEIRO,
        )
        for pedido in operacionais:
            self.assertTrue(
                pedido.liberado_financeiramente,
                f"Pedido #{pedido.pk} bloqueado financeiramente",
            )

    def test_parcelas_de_pedidos_faturados(self):
        call_command("popular_demo_estamparia")
        faturados = Pedido.objects.filter(
            empresa=self.empresa,
            versao_termos__startswith="demo-estamparia",
            status_financeiro=Pedido.StatusFinanceiro.FATURADO_ATACADO,
        )
        self.assertTrue(faturados.exists())
        for pedido in faturados:
            parcelas = ContaReceber.objects.filter(pedido=pedido)
            self.assertGreaterEqual(parcelas.count(), 1)
            total = sum((p.valor for p in parcelas), start=0)
            self.assertAlmostEqual(float(total), float(pedido.valor_total), places=2)

    def test_clean_remove_apenas_demo(self):
        call_command("popular_demo_estamparia")
        call_command("popular_demo_estamparia", "--clean")
        contagens = self._contagens()
        self.assertEqual(contagens["categorias"], 0)
        self.assertEqual(contagens["modelos"], 0)
        self.assertEqual(contagens["skus"], 0)
        self.assertEqual(contagens["clientes"], 0)
        self.assertEqual(contagens["pedidos"], 0)
        self.assertEqual(contagens["itens"], 0)
        self.assertEqual(contagens["a_receber"], 0)
        self.assertEqual(contagens["a_pagar"], 0)
        self.assertEqual(contagens["caixa"], 0)
        # A empresa é preservada.
        self.assertTrue(Empresa.objects.filter(pk=self.empresa.pk).exists())
