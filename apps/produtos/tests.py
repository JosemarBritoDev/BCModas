from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase

from apps.clientes.models import Cliente
from apps.produtos.models import Categoria, Modelo, SKU
from apps.tenants.models import Empresa


def criar_empresa(nome="Confecção Teste", cnpj="00.000.000/0001-00"):
    return Empresa.objects.create(
        nome_fantasia=nome,
        cnpj=cnpj,
        status=Empresa.Status.ATIVO,
        whatsapp_comercial="(11) 99999-9999",
    )


class PrecoAtacadoVarejoTests(TestCase):
    def setUp(self):
        self.empresa = criar_empresa()
        self.modelo = Modelo.objects.create(
            empresa=self.empresa,
            nome="Camiseta Teste",
            preco_varejo=Decimal("60.00"),
            preco_atacado=Decimal("40.00"),
            qtd_minima_atacado=6,
        )

    def test_tem_atacado_quando_preco_positivo(self):
        self.assertTrue(self.modelo.tem_atacado)

    def test_preco_varejo_abaixo_da_quantidade_minima(self):
        self.assertEqual(self.modelo.preco_unitario_para(1), Decimal("60.00"))
        self.assertEqual(self.modelo.preco_unitario_para(5), Decimal("60.00"))

    def test_preco_atacado_a_partir_da_quantidade_minima(self):
        self.assertEqual(self.modelo.preco_unitario_para(6), Decimal("40.00"))
        self.assertEqual(self.modelo.preco_unitario_para(24), Decimal("40.00"))

    def test_sem_preco_atacado_usa_varejo(self):
        self.modelo.preco_atacado = Decimal("0.00")
        self.assertFalse(self.modelo.tem_atacado)
        self.assertEqual(self.modelo.preco_unitario_para(100), Decimal("60.00"))

    def test_quantidade_invalida_usa_varejo(self):
        self.assertEqual(self.modelo.preco_unitario_para(None), Decimal("60.00"))


class PopulateDemoDataTests(TestCase):
    def test_popula_ao_menos_dez_produtos_com_grade_e_precos(self):
        call_command("populate_demo_data", verbosity=0)
        modelos = Modelo.objects.all()
        self.assertGreaterEqual(modelos.count(), 10)
        self.assertGreaterEqual(SKU.objects.count(), 30)

        for modelo in modelos:
            self.assertGreater(modelo.preco_varejo, Decimal("0"))
            self.assertGreater(modelo.preco_atacado, Decimal("0"))
            self.assertGreaterEqual(modelo.qtd_minima_atacado, 1)
            self.assertTrue(modelo.skus.exists())

    def test_comando_e_idempotente(self):
        call_command("populate_demo_data", verbosity=0)
        total = Modelo.objects.count()
        call_command("populate_demo_data", verbosity=0)
        self.assertEqual(Modelo.objects.count(), total)


class PopularDemoTests(TestCase):
    def setUp(self):
        self.empresa = criar_empresa()

    def test_popula_categorias_produtos_e_clientes(self):
        call_command("popular_demo", verbosity=0)

        self.assertEqual(Categoria.objects.filter(empresa=self.empresa).count(), 4)
        modelos = Modelo.objects.filter(empresa=self.empresa)
        self.assertEqual(modelos.count(), 12)
        self.assertEqual(Cliente.objects.count(), 6)

        for modelo in modelos:
            self.assertTrue(modelo.skus.exists())
            self.assertTrue(modelo.fotos_urls)
            self.assertTrue(modelo.fotos_urls[0].startswith("https://"))

        for cliente in Cliente.objects.all():
            self.assertFalse(cliente.has_usable_password())
            self.assertTrue(cliente.documento_limpo())

    def test_comando_e_idempotente(self):
        call_command("popular_demo", verbosity=0)
        call_command("popular_demo", verbosity=0)

        self.assertEqual(Modelo.objects.count(), 12)
        self.assertEqual(SKU.objects.filter(empresa=self.empresa).count(), 168)
        self.assertEqual(Cliente.objects.count(), 6)
        self.assertEqual(Categoria.objects.count(), 4)

    def test_clean_remove_apenas_dados_de_demonstracao(self):
        outro_modelo = Modelo.objects.create(
            empresa=self.empresa, nome="Produto Real", preco_varejo=Decimal("10.00")
        )
        outro_cliente = Cliente.objects.create_cliente(
            email="real@empresa.com",
            nome_razao_social="Cliente Real",
            whatsapp="(11) 90000-0000",
            empresa=self.empresa,
        )
        call_command("popular_demo", verbosity=0)
        self.assertEqual(Modelo.objects.filter(empresa=self.empresa).count(), 13)

        call_command("popular_demo", clean=True, verbosity=0)

        self.assertTrue(Empresa.objects.filter(pk=self.empresa.pk).exists())
        self.assertTrue(Modelo.objects.filter(pk=outro_modelo.pk).exists())
        self.assertTrue(Cliente.objects.filter(pk=outro_cliente.pk).exists())
        self.assertEqual(Modelo.objects.filter(empresa=self.empresa).count(), 1)
        self.assertEqual(Cliente.objects.count(), 1)
        self.assertEqual(Categoria.objects.filter(empresa=self.empresa).count(), 0)
