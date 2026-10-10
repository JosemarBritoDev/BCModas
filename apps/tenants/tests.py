from django.test import TestCase
from django.urls import reverse

from apps.tenants.models import Empresa
from apps.usuarios.models import Usuario


class EmpresaUnicaTests(TestCase):
    def _criar(self, nome, cnpj, status):
        return Empresa.objects.create(
            nome_fantasia=nome,
            cnpj=cnpj,
            email=f"{nome.lower()}@fabrica.com.br",
            whatsapp_comercial="(11) 99999-0000",
            status=status,
        )

    def test_obter_fabrica_prefere_ativa(self):
        self._criar("Suspensa", "22.222.222/0001-22", Empresa.Status.SUSPENSO)
        ativa = self._criar("Ativa", "33.333.333/0001-33", Empresa.Status.ATIVO)
        self.assertEqual(Empresa.obter_fabrica(), ativa)

    def test_obter_fabrica_sem_ativa_retorna_primeira(self):
        suspensa = self._criar("Suspensa", "44.444.444/0001-44", Empresa.Status.SUSPENSO)
        self.assertEqual(Empresa.obter_fabrica(), suspensa)

    def test_admin_redireciona_para_edicao_unica(self):
        empresa = self._criar("Fábrica Única", "55.555.555/0001-55", Empresa.Status.ATIVO)
        admin = Usuario.objects.create_superuser(
            username="admin", email="admin@fabrica.com.br", password="SenhaForte123"
        )
        self.client.force_login(admin)
        resp = self.client.get("/admin/tenants/empresa/")
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(
            resp.headers["Location"],
            reverse("admin:tenants_empresa_change", args=[empresa.pk]),
        )

    def test_admin_com_varias_fabricas_abre_a_ativa(self):
        self._criar("Antiga", "66.666.666/0001-66", Empresa.Status.SUSPENSO)
        ativa = self._criar("Atual", "77.777.777/0001-77", Empresa.Status.ATIVO)
        admin = Usuario.objects.create_superuser(
            username="admin3", email="admin3@fabrica.com.br", password="SenhaForte123"
        )
        self.client.force_login(admin)
        resp = self.client.get("/admin/tenants/empresa/")
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(
            resp.headers["Location"],
            reverse("admin:tenants_empresa_change", args=[ativa.pk]),
        )

    def test_admin_sem_fabrica_redireciona_para_cadastro(self):
        admin = Usuario.objects.create_superuser(
            username="admin2", email="admin2@fabrica.com.br", password="SenhaForte123"
        )
        self.client.force_login(admin)
        resp = self.client.get("/admin/tenants/empresa/")
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.headers["Location"], reverse("admin:tenants_empresa_add"))
