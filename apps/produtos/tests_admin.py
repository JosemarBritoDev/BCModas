"""Testes de regressão do admin: criação de registros e botões de pop-up.

Cobrem a revisão dos bloqueios causados por ``autocomplete_fields`` e pelos
mixins de escopo/RBAC, garantindo que o superusuário consiga criar Empresa,
Categoria, Cliente, Modelo e SKU diretamente pela interface do Unfold.
"""

from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.clientes.admin import ClienteAdmin
from apps.clientes.models import Cliente
from apps.financeiro.admin import CaixaMovimentacaoAdmin, ContaReceberAdmin
from apps.pedidos.admin import ItemPedidoInline, PedidoAdmin
from apps.produtos.admin import CategoriaAdmin, ModeloAdmin, SKUAdmin
from apps.produtos.models import Categoria, Modelo, SKU
from apps.tenants.models import Empresa
from apps.usuarios.models import Usuario

ADMINS_SEM_AUTOCOMPLETE = (
    CategoriaAdmin,
    ModeloAdmin,
    SKUAdmin,
    ClienteAdmin,
    ContaReceberAdmin,
    CaixaMovimentacaoAdmin,
    PedidoAdmin,
    ItemPedidoInline,
)


class SemAutocompleteTests(TestCase):
    """Garante que nenhum admin volta a desabilitar os pop-ups nativos."""

    def test_admins_operacionais_sem_autocomplete(self):
        for admin_class in ADMINS_SEM_AUTOCOMPLETE:
            with self.subTest(admin=admin_class.__name__):
                self.assertEqual(
                    list(getattr(admin_class, "autocomplete_fields", [])),
                    [],
                )


class AdminCriacaoTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            nome_fantasia="Fábrica Teste",
            cnpj="11.111.111/0001-11",
            email="fabrica@teste.com",
            whatsapp_comercial="(11) 99999-0000",
        )
        self.admin = Usuario.objects.create_superuser(
            username="root",
            email="root@teste.com",
            password="SenhaForte123",
        )
        self.client.force_login(self.admin)

    def test_get_paginas_de_cadastro(self):
        for url_name in (
            "admin:produtos_categoria_add",
            "admin:clientes_cliente_add",
            "admin:produtos_modelo_add",
            "admin:produtos_sku_add",
            "admin:pedidos_pedido_add",
            "admin:financeiro_contareceber_add",
        ):
            with self.subTest(url=url_name):
                resp = self.client.get(reverse(url_name))
                self.assertEqual(resp.status_code, 200)

    def test_criar_categoria(self):
        resp = self.client.post(
            reverse("admin:produtos_categoria_add"),
            {
                "empresa": self.empresa.pk,
                "nome": "Camisetas",
                "ordem": 1,
                "ativo": "on",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Categoria.objects.count(), 1)

    def test_criar_cliente(self):
        resp = self.client.post(
            reverse("admin:clientes_cliente_add"),
            {
                "empresa": self.empresa.pk,
                "nome_razao_social": "Cliente Teste",
                "tipo_pessoa": "PF",
                "whatsapp": "(11) 98888-0000",
                "email": "cliente@teste.com",
                "is_active": "on",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Cliente.objects.count(), 1)

    def test_criar_modelo_com_sku_inline(self):
        resp = self.client.post(
            reverse("admin:produtos_modelo_add"),
            {
                "empresa": self.empresa.pk,
                "nome": "Camiseta Premium",
                "preco_varejo": "59.90",
                "preco_atacado": "39.90",
                "qtd_minima_atacado": "6",
                "avaliacao": "4.5",
                "skus-TOTAL_FORMS": "1",
                "skus-INITIAL_FORMS": "0",
                "skus-MIN_NUM_FORMS": "0",
                "skus-MAX_NUM_FORMS": "1000",
                "skus-0-cor_nome": "Preto",
                "skus-0-cor_hex": "#000000",
                "skus-0-tamanho": "M",
                "skus-0-quantidade_estoque": "10",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Modelo.objects.count(), 1)
        self.assertEqual(SKU.objects.count(), 1)

    def test_criar_empresa_quando_nao_existe(self):
        Empresa.objects.all().delete()
        resp = self.client.get(reverse("admin:tenants_empresa_add"))
        self.assertEqual(resp.status_code, 200)
        resp = self.client.post(
            reverse("admin:tenants_empresa_add"),
            {
                "nome_fantasia": "Nova Fábrica",
                "cnpj": "22.222.222/0001-22",
                "email": "nova@fabrica.com",
                "whatsapp_comercial": "(11) 97777-0000",
                "status": Empresa.Status.ATIVO,
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Empresa.objects.count(), 1)
        empresa = Empresa.objects.first()
        self.assertEqual(empresa.slug, "nova-fabrica")
        self.assertEqual(empresa.cor_primaria, "#111827")
        self.assertEqual(str(empresa.taxa_entrega_padrao), "0.00")

    def test_empresa_add_bloqueado_quando_ja_existe(self):
        resp = self.client.get(reverse("admin:tenants_empresa_add"))
        self.assertEqual(resp.status_code, 403)

    def test_botoes_popup_presentes_nos_formularios(self):
        # Categoria vinculada ao Modelo e Modelo vinculado ao SKU exibem o
        # menu de ações rápidas (pop-up) do modelo relacionado.
        html_modelo = self.client.get(reverse("admin:produtos_modelo_add")).content.decode()
        self.assertIn("related-widget-wrapper", html_modelo)
        self.assertIn("add-related", html_modelo)

        html_sku = self.client.get(reverse("admin:produtos_sku_add")).content.decode()
        self.assertIn("add-related", html_sku)

        html_pedido = self.client.get(reverse("admin:pedidos_pedido_add")).content.decode()
        self.assertIn("add-related", html_pedido)


class EmpresaScopedMixinTests(TestCase):
    """O mixin não deve bloquear silenciosamente a criação pelo superusuário."""

    def test_save_model_atribui_fabrica_unica_quando_ausente(self):
        fabrica = Empresa.objects.create(
            nome_fantasia="Fábrica Única",
            cnpj="33.333.333/0001-33",
            email="unica@fabrica.com",
            whatsapp_comercial="(11) 96666-0000",
        )
        admin = Usuario.objects.create_superuser(
            username="root2",
            email="root2@teste.com",
            password="SenhaForte123",
        )
        request = RequestFactory().post("/admin/produtos/categoria/add/")
        request.user = admin
        categoria = Categoria(nome="Sem Empresa no Form")
        CategoriaAdmin(Categoria, AdminSite()).save_model(
            request, categoria, form=None, change=False
        )
        self.assertEqual(categoria.empresa, fabrica)

    def test_empresa_preselecionada_para_usuario_nao_superadmin(self):
        empresa = Empresa.objects.create(
            nome_fantasia="Fábrica do Gerente",
            cnpj="44.444.444/0001-44",
            email="gerente@fabrica.com",
            whatsapp_comercial="(11) 95555-0000",
        )
        gerente = Usuario.objects.create_user(
            username="ger",
            email="ger@teste.com",
            password="SenhaForte123",
            role=Usuario.Role.GERENTE,
            empresa=empresa,
        )
        request = RequestFactory().get("/admin/produtos/categoria/add/")
        request.user = gerente
        admin = CategoriaAdmin(Categoria, AdminSite())
        field = admin.formfield_for_foreignkey(
            Categoria._meta.get_field("empresa"), request
        )
        self.assertEqual(list(field.queryset), [empresa])
        self.assertEqual(field.initial, empresa.pk)

    def test_financeiro_nao_acessa_admin_de_produtos(self):
        financeiro = Usuario.objects.create_user(
            username="fin",
            email="fin@teste.com",
            password="SenhaForte123",
            role=Usuario.Role.FINANCEIRO,
        )
        admin_sku = SKUAdmin(SKU, AdminSite())
        request = RequestFactory().get("/admin/produtos/sku/")
        request.user = financeiro
        self.assertFalse(admin_sku.has_module_permission(request))


class EdicaoPorPerfilTests(TestCase):
    """Perfis gerenciais devem criar/alterar/excluir, não só visualizar.

    Reproduz a queixa de telas "congeladas" no admin de Categoria e Empresa:
    garante botões de adicionar/alterar e formulário editável (com Save).
    """

    def setUp(self):
        self.empresa = Empresa.objects.create(
            nome_fantasia="Fábrica Perfis",
            cnpj="55.555.555/0001-55",
            email="perfis@fabrica.com",
            whatsapp_comercial="(11) 94444-0000",
        )
        self.categoria = Categoria.objects.create(
            empresa=self.empresa, nome="Categoria Base", slug="categoria-base"
        )

    def _login(self, role):
        user = Usuario.objects.create_user(
            username=f"perfil_{role}",
            email=f"perfil_{role}@fabrica.com",
            password="SenhaForte123",
            role=role,
            is_staff=True,
            empresa=self.empresa,
        )
        self.client.force_login(user)
        return user

    def test_changelist_categoria_com_acoes(self):
        for role in ("SUPERADMIN", "GERENTE"):
            with self.subTest(role=role):
                self._login(role)
                html = self.client.get(
                    reverse("admin:produtos_categoria_changelist")
                ).content.decode()
                self.assertIn("addlink", html)
                self.assertIn(
                    reverse(
                        "admin:produtos_categoria_change", args=[self.categoria.pk]
                    ),
                    html,
                )

    def test_formulario_empresa_editavel(self):
        for role in ("SUPERADMIN", "GERENTE"):
            with self.subTest(role=role):
                self._login(role)
                resp = self.client.get(
                    reverse("admin:tenants_empresa_change", args=[self.empresa.pk])
                )
                self.assertEqual(resp.status_code, 200)
                html = resp.content.decode()
                self.assertIn('name="_save"', html)
                # O nome fantasia deve ser editável (não "congelado").
                trecho = html[
                    html.find('name="nome_fantasia"') : html.find(
                        'name="nome_fantasia"'
                    )
                    + 300
                ]
                self.assertNotIn("readonly", trecho)

    def test_superusuario_tem_acesso_total(self):
        admin = Usuario.objects.create_superuser(
            username="root_total",
            email="root_total@fabrica.com",
            password="SenhaForte123",
        )
        for admin_class, model in (
            (CategoriaAdmin, Categoria),
            (ModeloAdmin, Modelo),
            (SKUAdmin, SKU),
            (ClienteAdmin, Cliente),
        ):
            with self.subTest(admin=admin_class.__name__):
                request = RequestFactory().get("/admin/")
                request.user = admin
                instance = admin_class(model, AdminSite())
                self.assertTrue(instance.has_add_permission(request))
                self.assertTrue(instance.has_change_permission(request))
                self.assertTrue(instance.has_delete_permission(request))
