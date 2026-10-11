"""Testes do Assistente de IA do ERP (Silk): RBAC, manuais e endpoint."""

import json
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from apps.usuarios.models import Usuario
from apps.core.services.help_assistant import HelpAssistantService


def _usuario(username, role, **extra):
    return Usuario.objects.create_user(
        username=username,
        email=f"{username}@teste.com",
        password="SenhaForte123",
        role=role,
        **extra,
    )


class ManuaisDisponiveisTests(TestCase):
    def test_manuais_markdown_existem(self):
        for relativo in HelpAssistantService.MANUAIS.values():
            with self.subTest(manual=relativo):
                caminho = Path(settings.BASE_DIR) / relativo
                self.assertTrue(caminho.exists(), f"Manual ausente: {relativo}")
                self.assertGreater(caminho.stat().st_size, 0)


class ModuloPorRotaTests(TestCase):
    def setUp(self):
        self.service = HelpAssistantService(_usuario("x", Usuario.Role.GERENTE), "/admin/")

    def test_mapeamento_de_rotas(self):
        casos = {
            "/admin/produtos/sku/": "produtos",
            "/admin/pedidos/pedido/": "pedidos",
            "/admin/clientes/cliente/": "pedidos",
            "/admin/financeiro/contareceber/": "financeiro",
            "/admin/usuarios/usuario/": "permissoes",
            "/admin/tenants/empresa/": "permissoes",
            "/admin/": None,
        }
        for rota, esperado in casos.items():
            with self.subTest(rota=rota):
                self.assertEqual(self.service.modulo_da_rota(rota), esperado)


class BloqueioPorRoleTests(TestCase):
    """A trava de segurança do Silk por perfil de acesso."""

    def test_vendas_bloqueado_na_rota_financeira(self):
        vendedor = _usuario("vendas", Usuario.Role.VENDAS)
        resultado = HelpAssistantService(vendedor, "/admin/financeiro/").responder(
            "Como fecho o caixa?"
        )
        self.assertTrue(resultado["bloqueado"])
        self.assertEqual(resultado["modulo"], "financeiro")
        self.assertIn("Vendas", resultado["resposta"])

    def test_vendas_bloqueado_por_palavra_chave_financeira(self):
        vendedor = _usuario("vendas", Usuario.Role.VENDAS)
        resultado = HelpAssistantService(vendedor, "/admin/produtos/").responder(
            "Onde vejo o fluxo de caixa?"
        )
        self.assertTrue(resultado["bloqueado"])
        self.assertEqual(resultado["modulo"], "financeiro")

    def test_financeiro_bloqueado_no_modulo_produtos(self):
        financeiro = _usuario("financeiro", Usuario.Role.FINANCEIRO)
        resultado = HelpAssistantService(financeiro, "/admin/produtos/").responder(
            "Como cadastro uma grade de SKUs?"
        )
        self.assertTrue(resultado["bloqueado"])
        self.assertEqual(resultado["modulo"], "produtos")

    def test_gerente_liberado_no_financeiro(self):
        gerente = _usuario("gerente", Usuario.Role.GERENTE)
        resultado = HelpAssistantService(gerente, "/admin/financeiro/").responder(
            "Como fecho o caixa?"
        )
        self.assertFalse(resultado["bloqueado"])
        self.assertEqual(resultado["modulo"], "financeiro")

    def test_auditor_tem_leitura_liberada(self):
        auditor = _usuario("auditor", Usuario.Role.AUDITOR)
        for rota, modulo in (
            ("/admin/financeiro/", "financeiro"),
            ("/admin/produtos/", "produtos"),
            ("/admin/usuarios/", "permissoes"),
        ):
            with self.subTest(rota=rota):
                resultado = HelpAssistantService(auditor, rota).responder("Ajuda?")
                self.assertFalse(resultado["bloqueado"])
                self.assertEqual(resultado["modulo"], modulo)

    def test_superusuario_tem_acesso_total(self):
        superuser = Usuario.objects.create_superuser(
            username="root", email="root@teste.com", password="SenhaForte123"
        )
        resultado = HelpAssistantService(superuser, "/admin/financeiro/").responder(
            "Como faço uma conta a pagar?"
        )
        self.assertFalse(resultado["bloqueado"])


class RespostaOfflineTests(TestCase):
    """Sem SILK_AI_API_KEY o assistente usa o manual como fallback."""

    def test_fallback_retorna_trecho_do_manual(self):
        with self.settings(SILK_AI_API_KEY=""):
            gerente = _usuario("gerente", Usuario.Role.GERENTE)
            resultado = HelpAssistantService(gerente, "/admin/financeiro/").responder(
                "Como registra uma despesa?"
            )
        self.assertFalse(resultado["bloqueado"])
        self.assertIsNone(resultado["fonte"])
        self.assertIn("manual", resultado["resposta"].lower())
        self.assertIn("Contas a Pagar", resultado["resposta"])

    def test_pergunta_vazia_nao_quebra(self):
        gerente = _usuario("gerente", Usuario.Role.GERENTE)
        resultado = HelpAssistantService(gerente, "/admin/").responder("")
        self.assertFalse(resultado["bloqueado"])
        self.assertIn("resposta", resultado)


class ChamadaIATests(TestCase):
    """A chamada HTTP usa o endpoint do Gemini e envia a chave por Bearer e URL."""

    class _RespostaFalsa:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(
                {"choices": [{"message": {"content": "resposta da IA"}}]}
            ).encode("utf-8")

    def test_envia_bearer_e_endpoint_gemini(self):
        gerente = _usuario("gerente", Usuario.Role.GERENTE)
        service = HelpAssistantService(gerente, "/admin/produtos/")
        capturado = {}

        def fake_urlopen(requisicao, timeout=None):
            capturado["url"] = requisicao.full_url
            capturado["headers"] = {
                chave.lower(): valor for chave, valor in requisicao.header_items()
            }
            return self._RespostaFalsa()

        with self.settings(SILK_AI_API_KEY="chave-teste"), mock.patch(
            "apps.core.services.help_assistant.urllib.request.urlopen",
            fake_urlopen,
        ):
            resultado = service.responder("Como cadastro um produto?")

        self.assertFalse(resultado["bloqueado"])
        self.assertEqual(resultado["resposta"], "resposta da IA")
        self.assertTrue(
            capturado["url"].startswith(
                "https://generativelanguage.googleapis.com/v1beta/openai/"
            )
        )
        self.assertIn("/chat/completions", capturado["url"])
        self.assertIn("key=chave-teste", capturado["url"])
        self.assertEqual(
            capturado["headers"]["authorization"], "Bearer chave-teste"
        )


class SaudacaoTests(TestCase):
    """Cumprimentos simples respondem direto no código, sem acionar a IA."""

    def setUp(self):
        self.service = HelpAssistantService(
            _usuario("gerente", Usuario.Role.GERENTE), "/admin/"
        )

    def test_saudacoes_retornam_resposta_amigavel(self):
        respostas = ("oi", "olá", "ola", "bom dia", "boa tarde", "boa noite", "Olá!")
        for saudacao in respostas:
            with self.subTest(saudacao=saudacao):
                resultado = self.service.responder(saudacao)
                self.assertFalse(resultado["bloqueado"])
                self.assertIsNone(resultado["fonte"])
                self.assertEqual(
                    resultado["resposta"],
                    HelpAssistantService.SAUDACAO_RESPOSTA,
                )

    def test_frase_contendo_palavra_nao_conta_como_saudacao(self):
        self.service.current_path = "/admin/"
        self.assertFalse(self.service.e_saudacao("foi cadastrado?"))
        resultado = self.service.responder("como cadastro um produto?")
        self.assertNotEqual(
            resultado["resposta"], HelpAssistantService.SAUDACAO_RESPOSTA
        )


class SilkEndpointTests(TestCase):
    def setUp(self):
        self.url = reverse("silk_help")
        self.vendedor = _usuario("vendas", Usuario.Role.VENDAS, is_staff=True)
        self.gerente = _usuario("gerente", Usuario.Role.GERENTE, is_staff=True)

    def test_exige_login(self):
        resp = self.client.post(self.url, {"pergunta": "oi", "rota": "/admin/"})
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/admin/login", resp.url)

    def test_get_nao_permitido(self):
        self.client.force_login(self.gerente)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 405)

    def test_post_retorna_json_com_resposta(self):
        self.client.force_login(self.gerente)
        resp = self.client.post(
            self.url, {"pergunta": "Como cadastro um produto?", "rota": "/admin/produtos/"}
        )
        self.assertEqual(resp.status_code, 200)
        dados = resp.json()
        self.assertFalse(dados["bloqueado"])
        self.assertEqual(dados["modulo"], "produtos")
        self.assertTrue(dados["resposta"])

    def test_post_bloqueia_vendas_no_financeiro(self):
        self.client.force_login(self.vendedor)
        resp = self.client.post(
            self.url,
            {"pergunta": "Como vejo o caixa?", "rota": "/admin/financeiro/"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["bloqueado"])

    def test_post_aceita_json(self):
        self.client.force_login(self.gerente)
        resp = self.client.post(
            self.url,
            data='{"pergunta": "ajuda", "rota": "/admin/produtos/"}',
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)

    def test_pergunta_vazia_retorna_400(self):
        self.client.force_login(self.gerente)
        resp = self.client.post(self.url, {"pergunta": "  ", "rota": "/admin/"})
        self.assertEqual(resp.status_code, 400)


class SilkWidgetInjectionTests(TestCase):
    def test_widget_aparece_no_admin_para_usuario_logado(self):
        gerente = _usuario("gerente", Usuario.Role.GERENTE, is_staff=True)
        self.client.force_login(gerente)
        resp = self.client.get(reverse("admin:index"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "silk-widget")
        self.assertContains(resp, reverse("silk_help"))

    def test_widget_aparece_nas_telas_de_listagem_e_edicao(self):
        superuser = Usuario.objects.create_superuser(
            username="root", email="root@teste.com", password="SenhaForte123"
        )
        self.client.force_login(superuser)
        for nome, url in (
            ("listagem", reverse("admin:produtos_modelo_changelist")),
            ("edição", reverse("admin:produtos_modelo_add")),
        ):
            with self.subTest(tela=nome):
                resp = self.client.get(url)
                self.assertEqual(resp.status_code, 200)
                self.assertContains(resp, "silk-widget")
                self.assertContains(resp, reverse("silk_help"))
