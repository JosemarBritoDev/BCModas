from django.test import TestCase
from django.urls import reverse

from apps.tenants.models import Empresa

from .backends import ClienteBackend
from .models import Cliente


class ClienteModelTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            nome_fantasia="Fábrica Clientes",
            cnpj="00.000.000/0001-55",
            whatsapp_comercial="(11) 90000-0000",
            status=Empresa.Status.ATIVO,
        )

    def test_create_cliente_gera_senha_hasheada(self):
        cliente = Cliente.objects.create_cliente(
            email="cliente@teste.com",
            password="SenhaForte123",
            empresa=self.empresa,
            nome_razao_social="Cliente Teste",
            whatsapp="11999999999",
        )
        self.assertNotEqual(cliente.password, "SenhaForte123")
        self.assertTrue(cliente.check_password("SenhaForte123"))
        self.assertTrue(cliente.is_cliente)

    def test_documento_limpo_remove_mascara(self):
        cliente = Cliente(
            nome_razao_social="X",
            email="x@x.com",
            whatsapp="1",
            cpf_cnpj="123.456.789-00",
        )
        self.assertEqual(cliente.documento_limpo(), "12345678900")

    def test_email_unico(self):
        Cliente.objects.create_cliente(
            email="unico@teste.com",
            password="SenhaForte123",
            empresa=self.empresa,
            nome_razao_social="A",
            whatsapp="1",
        )
        with self.assertRaises(Exception):
            Cliente.objects.create_cliente(
                email="unico@teste.com",
                password="SenhaForte123",
                empresa=self.empresa,
                nome_razao_social="B",
                whatsapp="2",
            )


class ClienteBackendTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            nome_fantasia="Fábrica Backend",
            cnpj="00.000.000/0001-66",
            whatsapp_comercial="(11) 90000-0000",
            status=Empresa.Status.ATIVO,
        )
        self.cliente = Cliente.objects.create_cliente(
            email="backend@teste.com",
            password="SenhaForte123",
            empresa=self.empresa,
            nome_razao_social="Backend",
            whatsapp="11999999999",
        )
        self.backend = ClienteBackend()

    def test_autentica_credenciais_validas(self):
        self.assertEqual(
            self.backend.authenticate(None, username="backend@teste.com", password="SenhaForte123"),
            self.cliente,
        )

    def test_rejeita_senha_invalida(self):
        self.assertIsNone(
            self.backend.authenticate(None, username="backend@teste.com", password="errada")
        )

    def test_rejeita_email_inexistente(self):
        self.assertIsNone(
            self.backend.authenticate(None, username="nao@existe.com", password="SenhaForte123")
        )

    def test_get_user(self):
        self.assertEqual(self.backend.get_user(self.cliente.pk), self.cliente)
        self.assertIsNone(self.backend.get_user(999999))


class CatalogoAcessoViewTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            nome_fantasia="Fábrica Acesso",
            cnpj="00.000.000/0001-77",
            whatsapp_comercial="(11) 90000-0000",
            status=Empresa.Status.ATIVO,
        )

    def test_get_cadastro_retorna_200(self):
        url = reverse("catalogo_cliente_cadastro", kwargs={"slug": self.empresa.slug})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_cadastro_cria_cliente_e_loga(self):
        url = reverse("catalogo_cliente_cadastro", kwargs={"slug": self.empresa.slug})
        resp = self.client.post(
            url,
            {
                "nome_razao_social": "Nova Loja",
                "tipo_pessoa": "PJ",
                "cpf_cnpj": "11.222.333/0001-44",
                "whatsapp": "(11) 98888-7777",
                "email": "novaloja@teste.com",
                "cep": "01001-000",
                "endereco": "Rua A",
                "numero": "100",
                "bairro": "Centro",
                "cidade": "São Paulo",
                "estado": "SP",
                "senha": "SenhaForte123",
                "senha_confirma": "SenhaForte123",
            },
        )
        self.assertEqual(resp.status_code, 302)
        cliente = Cliente.objects.get(email="novaloja@teste.com")
        self.assertEqual(cliente.cpf_cnpj, "11222333000144")
        self.assertEqual(cliente.whatsapp, "11988887777")
        self.assertEqual(self.client.session["_auth_user_backend"], "apps.clientes.backends.ClienteBackend")

    def test_cadastro_senhas_diferentes_falha(self):
        url = reverse("catalogo_cliente_cadastro", kwargs={"slug": self.empresa.slug})
        self.client.post(
            url,
            {
                "nome_razao_social": "Nova Loja",
                "tipo_pessoa": "PF",
                "whatsapp": "11988887777",
                "email": "novaloja2@teste.com",
                "senha": "SenhaForte123",
                "senha_confirma": "OutraSenha123",
            },
        )
        self.assertFalse(Cliente.objects.filter(email="novaloja2@teste.com").exists())

    def test_login_valido_autentica(self):
        Cliente.objects.create_cliente(
            email="login@teste.com",
            password="SenhaForte123",
            empresa=self.empresa,
            nome_razao_social="Login",
            whatsapp="11999999999",
        )
        url = reverse("catalogo_cliente_login", kwargs={"slug": self.empresa.slug})
        resp = self.client.post(url, {"email": "login@teste.com", "senha": "SenhaForte123"})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self.client.session["_auth_user_backend"], "apps.clientes.backends.ClienteBackend")

    def test_login_invalido_nao_autentica(self):
        url = reverse("catalogo_cliente_login", kwargs={"slug": self.empresa.slug})
        resp = self.client.post(url, {"email": "nao@existe.com", "senha": "SenhaForte123"})
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_empresa_suspensa_bloqueia_acesso(self):
        self.empresa.status = Empresa.Status.SUSPENSO
        self.empresa.save()
        url = reverse("catalogo_cliente_login", kwargs={"slug": self.empresa.slug})
        self.assertEqual(self.client.get(url).status_code, 403)
