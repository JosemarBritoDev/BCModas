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
            "/admin/clientes/cliente/": "clientes",
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


class ModoGuiadoTests(TestCase):
    """FAQ Interativo: perguntas padrão retornam respostas curtas, sem IA."""

    PERGUNTAS = {
        "visao_geral": "O que é esta tela?",
        "cadastrar": "Como cadastrar?",
        "regras": "Regras de negócio",
    }
    ROTAS = {
        "produtos": "/admin/produtos/modelo/",
        "pedidos": "/admin/pedidos/pedido/",
        "financeiro": "/admin/financeiro/contareceber/",
        "permissoes": "/admin/usuarios/usuario/",
        "clientes": "/admin/clientes/cliente/",
    }

    #: Perguntas específicas de cada módulo (FAQ expandido por tela).
    FAQ = {
        "produtos": {
            "/admin/produtos/modelo/": {
                "sku": "O que é um SKU?",
                "precos": "Diferença de preço Varejo/Atacado",
            },
        },
        "pedidos": {
            "/admin/pedidos/pedido/": {
                "status_pedido": "Fluxo de status",
                "trava_financeira": "O que é a Trava Financeira?",
                "cancelar_pedido": "Como cancelar um pedido?",
                "associar_cliente": "Como associar um cliente?",
            },
        },
        "clientes": {
            "/admin/clientes/cliente/": {
                "pf_pj": "Pessoa Física vs Jurídica",
                "historico_cliente": "Onde vejo o histórico?",
                "inativar_cliente": "Inativar cliente",
            },
        },
        "financeiro": {
            "/admin/financeiro/contareceber/": {
                "baixa_conta": "Como dar baixa numa conta?",
                "caixa_pedidos": "O que é o Caixa de Pedidos?",
                "estorno": "Estorno de valores",
            },
        },
        "permissoes": {
            "/admin/usuarios/usuario/": {
                "role": "O que é uma role?",
            },
        },
    }

    def test_respostas_curtas_dos_botoes(self):
        gerente = _usuario("gerente", Usuario.Role.GERENTE)
        for modulo, rota in self.ROTAS.items():
            for chave, pergunta in self.PERGUNTAS.items():
                with self.subTest(modulo=modulo, chave=chave):
                    resultado = HelpAssistantService(gerente, rota).responder(pergunta)
                    self.assertFalse(resultado["bloqueado"])
                    self.assertIsNone(resultado["fonte"])
                    self.assertEqual(resultado["modulo"], modulo)
                    self.assertEqual(
                        resultado["resposta"],
                        HelpAssistantService.RESPOSTAS_CURTAS[modulo][chave],
                    )

    def test_faq_especifico_por_modulo(self):
        gerente = _usuario("gerente", Usuario.Role.GERENTE)
        for modulo, rotas in self.FAQ.items():
            for rota, perguntas in rotas.items():
                for chave, pergunta in perguntas.items():
                    with self.subTest(modulo=modulo, chave=chave):
                        resultado = HelpAssistantService(gerente, rota).responder(
                            pergunta
                        )
                        self.assertFalse(resultado["bloqueado"])
                        self.assertIsNone(resultado["fonte"])
                        self.assertEqual(resultado["modulo"], modulo)
                        self.assertEqual(
                            resultado["resposta"],
                            HelpAssistantService.RESPOSTAS_CURTAS[modulo][chave],
                        )

    def test_dashboard_faq(self):
        gerente = _usuario("gerente", Usuario.Role.GERENTE)
        casos = {
            "visao_geral": "O que é esta tela?",
            "resumo": "Resumo deste ecrã",
            "alertas": "Como ler os alertas?",
            "graficos": "Como os gráficos são atualizados?",
        }
        for chave, pergunta in casos.items():
            with self.subTest(chave=chave):
                resultado = HelpAssistantService(gerente, "/admin/").responder(pergunta)
                self.assertIsNone(resultado["modulo"])
                self.assertIsNone(resultado["fonte"])
                self.assertEqual(
                    resultado["resposta"],
                    HelpAssistantService.RESPOSTAS_CURTAS["geral"][chave],
                )

    def test_variantes_modulares_dos_botoes(self):
        gerente = _usuario("gerente", Usuario.Role.GERENTE)
        casos = (
            ("produtos", "/admin/produtos/", "Como cadastrar?"),
            ("pedidos", "/admin/pedidos/", "Como criar um pedido?"),
            ("financeiro", "/admin/financeiro/", "Como registrar contas?"),
            ("permissoes", "/admin/usuarios/", "Como definir acesso?"),
        )
        for modulo, rota, pergunta in casos:
            with self.subTest(pergunta=pergunta):
                resultado = HelpAssistantService(gerente, rota).responder(pergunta)
                self.assertEqual(
                    resultado["resposta"],
                    HelpAssistantService.RESPOSTAS_CURTAS[modulo]["cadastrar"],
                )

    def test_texto_livre_nao_cai_no_modo_guiado(self):
        gerente = _usuario("gerente", Usuario.Role.GERENTE)
        resultado = HelpAssistantService(gerente, "/admin/produtos/").responder(
            "Como cadastro um produto no atacado?"
        )
        self.assertNotEqual(
            resultado["resposta"],
            HelpAssistantService.RESPOSTAS_CURTAS["produtos"]["cadastrar"],
        )
        self.assertIn("manual", resultado["resposta"].lower())

    def test_guia_respeita_trava_de_perfil(self):
        vendedor = _usuario("vendas", Usuario.Role.VENDAS)
        for pergunta in self.PERGUNTAS.values():
            with self.subTest(pergunta=pergunta):
                resultado = HelpAssistantService(
                    vendedor, "/admin/financeiro/"
                ).responder(pergunta)
                self.assertTrue(resultado["bloqueado"])
                self.assertEqual(resultado["modulo"], "financeiro")


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

    def test_post_retorna_resposta_curta_guiada(self):
        self.client.force_login(self.gerente)
        resp = self.client.post(
            self.url,
            {"pergunta": "O que é esta tela?", "rota": "/admin/produtos/"},
        )
        self.assertEqual(resp.status_code, 200)
        dados = resp.json()
        self.assertFalse(dados["bloqueado"])
        self.assertEqual(dados["modulo"], "produtos")
        self.assertEqual(
            dados["resposta"],
            HelpAssistantService.RESPOSTAS_CURTAS["produtos"]["visao_geral"],
        )

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

    def test_widget_inclui_botoes_de_acao_rapida(self):
        gerente = _usuario("gerente", Usuario.Role.GERENTE, is_staff=True)
        self.client.force_login(gerente)
        resp = self.client.get(reverse("admin:index"))
        self.assertContains(resp, "O que é esta tela?")
        self.assertContains(resp, "Como cadastrar?")
        self.assertContains(resp, "Regras de negócio")
        self.assertContains(resp, "Resumo deste ecrã")
        self.assertContains(resp, "Como ler os alertas?")
        self.assertContains(resp, "Como os gráficos são atualizados?")

    def test_widget_nao_tem_campo_de_digitacao(self):
        gerente = _usuario("gerente", Usuario.Role.GERENTE, is_staff=True)
        self.client.force_login(gerente)
        resp = self.client.get(reverse("admin:index"))
        self.assertNotContains(resp, 'id="silk-input"')
        self.assertNotContains(resp, "silk-input")
        self.assertNotContains(resp, "silk-send")
        self.assertNotContains(resp, "Pergunte sobre esta tela")

    def test_widget_index_faq_serve_respostas_da_dashboard(self):
        gerente = _usuario("gerente", Usuario.Role.GERENTE, is_staff=True)
        self.client.force_login(gerente)
        resp = self.client.post(
            reverse("silk_help"),
            {"pergunta": "Resumo deste ecrã", "rota": "/admin/"},
        )
        self.assertEqual(resp.status_code, 200)
        dados = resp.json()
        self.assertFalse(dados["bloqueado"])
        self.assertEqual(
            dados["resposta"],
            HelpAssistantService.RESPOSTAS_CURTAS["geral"]["resumo"],
        )

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
