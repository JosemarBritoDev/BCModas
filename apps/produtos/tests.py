from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase

from apps.produtos.models import Modelo, SKU
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
