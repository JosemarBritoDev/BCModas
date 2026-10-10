from decimal import Decimal

from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.clientes.models import Cliente
from apps.pedidos.admin import PedidoAdmin
from apps.pedidos.models import ItemPedido, Pedido
from apps.pedidos.views import _formatar_numero_whatsapp
from apps.produtos.models import Modelo, SKU
from apps.tenants.models import Empresa
from apps.usuarios.models import Usuario

BACKEND_CLIENTE = "apps.clientes.backends.ClienteBackend"


class FormatarNumeroWhatsappTests(TestCase):
    def test_adiciona_ddi_quando_falta(self):
        self.assertEqual(_formatar_numero_whatsapp("(11) 99999-9999"), "5511999999999")
        self.assertEqual(_formatar_numero_whatsapp("1133334444"), "551133334444")

    def test_preserva_ddi_existente(self):
        self.assertEqual(_formatar_numero_whatsapp("+55 11 99999-9999"), "5511999999999")

    def test_ddd_55_nao_e_confundido_com_ddi(self):
        self.assertEqual(_formatar_numero_whatsapp("(55) 99999-8888"), "5555999998888")

    def test_vazio(self):
        self.assertEqual(_formatar_numero_whatsapp(""), "")


class CatalogoFlowTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            nome_fantasia="Confecção Teste",
            cnpj="00.000.000/0001-00",
            status=Empresa.Status.ATIVO,
            whatsapp_comercial="(11) 99999-9999",
            termos_uso="Termos v1",
            politica_privacidade="Privacidade v1",
        )
        self.modelo = Modelo.objects.create(
            empresa=self.empresa,
            nome="Camiseta Básica",
            preco_varejo=Decimal("39.90"),
            visivel_catalogo=True,
        )
        self.sku = SKU.objects.create(
            empresa=self.empresa,
            modelo=self.modelo,
            cor_nome="Preto",
            cor_hex="#111111",
            tamanho=SKU.Tamanho.M,
            quantidade_estoque=10,
        )
        self.cliente = Cliente.objects.create_cliente(
            email="loja@cliente.com.br",
            password="SenhaForte123",
            empresa=self.empresa,
            nome_razao_social="Loja Cliente",
            tipo_pessoa=Cliente.TipoPessoa.PJ,
            cpf_cnpj="12345678000199",
            whatsapp="21988887777",
        )

    def _logar_cliente(self):
        self.client.force_login(self.cliente, backend=BACKEND_CLIENTE)

    def test_slug_gerado_automaticamente(self):
        self.assertEqual(self.empresa.slug, "confeccao-teste")

    def test_raiz_redireciona_para_catalogo_da_fabrica(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(
            resp.headers["Location"],
            reverse("catalogo_publico", kwargs={"slug": self.empresa.slug}),
        )

    def test_get_catalogo(self):
        url = reverse("catalogo_publico", kwargs={"slug": self.empresa.slug})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Camiseta Básica")
        self.assertIn("https://wa.me/5511999999999", resp.content.decode())

    def test_checkout_exige_login_do_cliente(self):
        url = reverse("catalogo_checkout", kwargs={"slug": self.empresa.slug})
        resp = self.client.post(
            url,
            {"aceite_lgpd": "on", f"qty_{self.sku.pk}": "1"},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp.headers["Location"])
        self.assertEqual(Pedido.objects.count(), 0)

    def test_checkout_cria_pedido_com_auditoria(self):
        self._logar_cliente()
        url = reverse("catalogo_checkout", kwargs={"slug": self.empresa.slug})
        resp = self.client.post(
            url,
            {"aceite_lgpd": "on", f"qty_{self.sku.pk}": "3"},
        )
        self.assertEqual(resp.status_code, 302)
        pedido = Pedido.objects.get()
        self.assertEqual(pedido.total_itens, 3)
        self.assertEqual(pedido.valor_total, Decimal("119.70"))
        self.assertTrue(pedido.aceite_lgpd)
        self.assertIsNotNone(pedido.data_aceite)
        self.assertTrue(pedido.versao_termos)
        self.assertEqual(pedido.itens.count(), 1)
        # dados cadastrais vinculados ao pedido
        self.assertEqual(pedido.cliente, self.cliente)
        self.assertEqual(pedido.cliente_nome, "Loja Cliente")
        self.assertEqual(pedido.cliente_documento, "12345678000199")
        # baixa automática de estoque
        self.sku.refresh_from_db()
        self.assertEqual(self.sku.quantidade_estoque, 7)

    def test_pagina_sucesso_gera_link_whatsapp_no_servidor(self):
        self.test_checkout_cria_pedido_com_auditoria()
        pedido = Pedido.objects.get()
        url = reverse(
            "catalogo_pedido_enviado",
            kwargs={"slug": self.empresa.slug, "pedido_id": pedido.pk},
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        conteudo = resp.content.decode()
        self.assertIn("https://wa.me/5511999999999?text=", conteudo)
        self.assertIn("NOVO%20PEDIDO", conteudo)

    def test_parametro_wa_forjado_e_ignorado(self):
        self.test_checkout_cria_pedido_com_auditoria()
        pedido = Pedido.objects.get()
        url = reverse(
            "catalogo_pedido_enviado",
            kwargs={"slug": self.empresa.slug, "pedido_id": pedido.pk},
        )
        resp = self.client.get(url, {"wa": "javascript:alert(1)"})
        self.assertNotIn("javascript:alert(1)", resp.content.decode())

    def test_pagina_sucesso_exige_sessao_do_pedido(self):
        pedido = Pedido.objects.create(
            empresa=self.empresa,
            cliente_nome="Loja Cliente",
            cliente_whatsapp="21988887777",
            aceite_lgpd=True,
        )
        url = reverse(
            "catalogo_pedido_enviado",
            kwargs={"slug": self.empresa.slug, "pedido_id": pedido.pk},
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)

    def test_checkout_sem_aceite_bloqueia(self):
        self._logar_cliente()
        url = reverse("catalogo_checkout", kwargs={"slug": self.empresa.slug})
        resp = self.client.post(url, {f"qty_{self.sku.pk}": "1"})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Pedido.objects.count(), 0)
        self.sku.refresh_from_db()
        self.assertEqual(self.sku.quantidade_estoque, 10)

    def test_checkout_sem_estoque_bloqueia(self):
        self._logar_cliente()
        url = reverse("catalogo_checkout", kwargs={"slug": self.empresa.slug})
        resp = self.client.post(
            url,
            {"aceite_lgpd": "on", f"qty_{self.sku.pk}": "999"},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Pedido.objects.count(), 0)
        self.sku.refresh_from_db()
        self.assertEqual(self.sku.quantidade_estoque, 10)

    def test_empresa_suspensa_403(self):
        self.empresa.status = Empresa.Status.SUSPENSO
        self.empresa.save()
        url = reverse("catalogo_publico", kwargs={"slug": self.empresa.slug})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)

    def test_isolamento_entre_empresas(self):
        outra = Empresa.objects.create(
            nome_fantasia="Outra Confecção",
            cnpj="11.111.111/0001-11",
            status=Empresa.Status.ATIVO,
            whatsapp_comercial="(31) 91111-2222",
        )
        outro_modelo = Modelo.objects.create(
            empresa=outra, nome="Calça Alheia", preco_varejo=Decimal("99.90")
        )
        outro_sku = SKU.objects.create(
            empresa=outra,
            modelo=outro_modelo,
            cor_nome="Azul",
            tamanho=SKU.Tamanho.G,
            quantidade_estoque=5,
        )
        self._logar_cliente()
        url = reverse("catalogo_checkout", kwargs={"slug": self.empresa.slug})
        self.client.post(
            url,
            {
                "aceite_lgpd": "on",
                f"qty_{outro_sku.pk}": "1",
                f"qty_{self.sku.pk}": "1",
            },
        )
        pedido = Pedido.objects.filter(empresa=self.empresa).first()
        self.assertIsNotNone(pedido)
        self.assertEqual(pedido.itens.count(), 1)
        self.assertEqual(pedido.itens.first().sku, self.sku)
        outro_sku.refresh_from_db()
        self.sku.refresh_from_db()
        self.assertEqual(outro_sku.quantidade_estoque, 5)
        self.assertEqual(self.sku.quantidade_estoque, 9)


class PedidoAdminTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            nome_fantasia="Fábrica Admin",
            cnpj="00.000.000/0001-77",
            email="admin@fabrica.com.br",
            whatsapp_comercial="(11) 90000-0000",
            status=Empresa.Status.ATIVO,
        )
        self.admin = PedidoAdmin(Pedido, AdminSite())

    def test_save_model_atribui_fabrica_padrao(self):
        usuario = Usuario.objects.create_user(username="operador", password="SenhaForte123")
        request = RequestFactory().post("/admin/pedidos/pedido/add/")
        request.user = usuario

        pedido = Pedido(cliente_nome="Lojista Manual", cliente_whatsapp="(11) 98888-0000")
        self.admin.save_model(request, pedido, form=None, change=False)

        self.assertEqual(pedido.empresa, self.empresa)
        self.assertTrue(Pedido.objects.filter(pk=pedido.pk, empresa=self.empresa).exists())

    def test_inline_de_itens_configurado(self):
        self.assertIn("ItemPedidoInline", [inline.__name__ for inline in self.admin.inlines])
        self.assertIn("id", self.admin.list_display_links)
        self.assertIn("cliente_nome", self.admin.list_display_links)

    def _request_para(self, usuario):
        request = RequestFactory().get("/admin/pedidos/pedido/")
        request.user = usuario
        return request

    def test_vendedor_nao_pode_adicionar_pedido(self):
        vendedor = Usuario.objects.create_user(
            username="vendedor", password="SenhaForte123", role=Usuario.Role.VENDAS
        )
        self.assertFalse(self.admin.has_add_permission(self._request_para(vendedor)))

    def test_gerente_pode_adicionar_pedido(self):
        gerente = Usuario.objects.create_user(
            username="gerente", password="SenhaForte123", role=Usuario.Role.GERENTE
        )
        self.assertTrue(self.admin.has_add_permission(self._request_para(gerente)))

    def test_vendedor_tem_campos_de_negocio_readonly(self):
        vendedor = Usuario.objects.create_user(
            username="vendedor2", password="SenhaForte123", role=Usuario.Role.VENDAS
        )
        readonly = self.admin.get_readonly_fields(self._request_para(vendedor))
        self.assertIn("total_itens", readonly)
        self.assertIn("valor_total", readonly)
        self.assertIn("cliente", readonly)

    def test_gerente_pode_editar_valores(self):
        gerente = Usuario.objects.create_user(
            username="gerente2", password="SenhaForte123", role=Usuario.Role.GERENTE
        )
        readonly = self.admin.get_readonly_fields(self._request_para(gerente))
        self.assertNotIn("total_itens", readonly)
        self.assertNotIn("valor_total", readonly)

    def test_admin_reserva_estoque_ao_criar_pedido(self):
        modelo = Modelo.objects.create(
            empresa=self.empresa, nome="Camiseta", preco_varejo=Decimal("10.00")
        )
        sku = SKU.objects.create(
            empresa=self.empresa,
            modelo=modelo,
            cor_nome="Preto",
            tamanho=SKU.Tamanho.M,
            quantidade_estoque=10,
        )
        pedido = Pedido.objects.create(
            empresa=self.empresa,
            cliente_nome="Lojista",
            cliente_whatsapp="11999999999",
        )
        ItemPedido.objects.create(
            pedido=pedido, sku=sku, quantidade=3, preco_unitario=Decimal("10.00")
        )

        class _FakeForm:
            def save_m2m(self):
                pass

        gerente = Usuario.objects.create_user(
            username="gerente3", password="SenhaForte123", role=Usuario.Role.GERENTE
        )
        form = _FakeForm()
        form.instance = pedido
        self.admin.save_related(self._request_para(gerente), form, [], change=False)

        sku.refresh_from_db()
        self.assertEqual(sku.quantidade_estoque, 7)
