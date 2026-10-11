"""Testes do perfil Somente Leitura (Auditor/Visitante)."""

from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.produtos.admin import CategoriaAdmin
from apps.produtos.models import Categoria
from apps.tenants.admin import EmpresaAdmin
from apps.tenants.models import Empresa
from apps.usuarios.models import Usuario


class IsAuditorPropertyTests(TestCase):
    def test_role_auditor_tem_is_auditor(self):
        auditor = Usuario.objects.create_user(
            username="auditor",
            email="auditor@teste.com",
            password="SenhaForte123",
            role=Usuario.Role.AUDITOR,
        )
        self.assertTrue(auditor.is_auditor)
        self.assertFalse(auditor.is_gerente)

    def test_outros_perfis_nao_sao_auditor(self):
        vendedor = Usuario.objects.create_user(
            username="vendas",
            email="vendas@teste.com",
            password="SenhaForte123",
            role=Usuario.Role.VENDAS,
        )
        self.assertFalse(vendedor.is_auditor)

    def test_superusuario_nunca_e_auditor(self):
        superuser = Usuario.objects.create_superuser(
            username="root",
            email="root@teste.com",
            password="SenhaForte123",
        )
        self.assertFalse(superuser.is_auditor)

    def test_choice_auditor_disponivel(self):
        self.assertIn(
            ("AUDITOR", "Auditor / Visitante"), Usuario.Role.choices
        )


class PerfilAdminMixinAuditorTests(TestCase):
    """O auditor enxerga tudo, mas nunca cria/altera/exclui."""

    def setUp(self):
        self.factory = RequestFactory()
        self.site = AdminSite()
        self.empresa_admin = EmpresaAdmin(Empresa, self.site)
        self.categoria_admin = CategoriaAdmin(Categoria, self.site)
        self.auditor = Usuario.objects.create_user(
            username="auditor",
            email="auditor@teste.com",
            password="SenhaForte123",
            role=Usuario.Role.AUDITOR,
            is_staff=True,
        )

    def _request(self, user):
        request = self.factory.get("/admin/")
        request.user = user
        return request

    def test_auditor_pode_ver_e_acessar_modulo_ignorando_perfis(self):
        request = self._request(self.auditor)
        # EmpresaAdmin restringe a SUPERADMIN/GERENTE; o auditor ainda enxerga.
        self.assertTrue(self.empresa_admin.has_module_permission(request))
        self.assertTrue(self.empresa_admin.has_view_permission(request))
        self.assertTrue(self.categoria_admin.has_module_permission(request))
        self.assertTrue(self.categoria_admin.has_view_permission(request))

    def test_auditor_nao_pode_editar(self):
        request = self._request(self.auditor)
        for admin_obj in (self.empresa_admin, self.categoria_admin):
            with self.subTest(admin=admin_obj.__class__.__name__):
                self.assertFalse(admin_obj.has_add_permission(request))
                self.assertFalse(admin_obj.has_change_permission(request))
                self.assertFalse(admin_obj.has_delete_permission(request))

    def test_superusuario_permanece_com_acesso_total(self):
        superuser = Usuario.objects.create_superuser(
            username="root",
            email="root@teste.com",
            password="SenhaForte123",
        )
        request = self._request(superuser)
        for admin_obj in (self.empresa_admin, self.categoria_admin):
            with self.subTest(admin=admin_obj.__class__.__name__):
                self.assertTrue(admin_obj.has_add_permission(request))
                self.assertTrue(admin_obj.has_change_permission(request))
                self.assertTrue(admin_obj.has_view_permission(request))
        # A exclusão da confecção é bloqueada para todos por regra de negócio,
        # mas o superusuário mantém exclusão em modelos operacionais.
        self.assertFalse(self.empresa_admin.has_delete_permission(request))
        self.assertTrue(self.categoria_admin.has_delete_permission(request))

    def test_perfil_comum_segue_regras_originais(self):
        vendedor = Usuario.objects.create_user(
            username="vendas",
            email="vendas@teste.com",
            password="SenhaForte123",
            role=Usuario.Role.VENDAS,
            is_staff=True,
        )
        request = self._request(vendedor)
        # VENDAS não está em perfis_permitidos da EmpresaAdmin.
        self.assertFalse(self.empresa_admin.has_view_permission(request))
        # Mas edita categorias normalmente (apenas FINANCEIRO é negado).
        self.assertTrue(self.categoria_admin.has_add_permission(request))
        self.assertTrue(self.categoria_admin.has_change_permission(request))


class AuditorAdminIntegrationTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            nome_fantasia="Fábrica Teste",
            cnpj="11.111.111/0001-11",
            email="fabrica@teste.com",
            whatsapp_comercial="(11) 99999-0000",
        )
        self.categoria = Categoria.objects.create(
            empresa=self.empresa, nome="Camisetas", slug="camisetas"
        )
        self.auditor = Usuario.objects.create_user(
            username="auditor",
            email="auditor@teste.com",
            password="SenhaForte123",
            role=Usuario.Role.AUDITOR,
            is_staff=True,
        )
        self.client.force_login(self.auditor)

    def test_auditor_visualiza_lista(self):
        resp = self.client.get(reverse("admin:produtos_categoria_changelist"))
        self.assertEqual(resp.status_code, 200)

    def test_auditor_nao_acessa_pagina_de_criacao(self):
        resp = self.client.get(reverse("admin:produtos_categoria_add"))
        self.assertEqual(resp.status_code, 403)

    def test_auditor_ve_pagina_de_alteracao_em_modo_leitura(self):
        resp = self.client.get(
            reverse("admin:produtos_categoria_change", args=[self.categoria.pk])
        )
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('name="_save"', resp.content.decode())

    def test_auditor_nao_altera_via_post(self):
        resp = self.client.post(
            reverse("admin:produtos_categoria_change", args=[self.categoria.pk]),
            {"empresa": self.empresa.pk, "nome": "Alterado", "ordem": 1, "ativo": "on"},
        )
        self.assertEqual(resp.status_code, 403)
        self.categoria.refresh_from_db()
        self.assertEqual(self.categoria.nome, "Camisetas")

    def test_auditor_nao_cria_via_post(self):
        resp = self.client.post(
            reverse("admin:produtos_categoria_add"),
            {"empresa": self.empresa.pk, "nome": "Hack", "ordem": 1, "ativo": "on"},
        )
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(Categoria.objects.filter(nome="Hack").exists())
