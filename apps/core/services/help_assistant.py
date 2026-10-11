"""Serviço de contexto e permissões do Assistente de IA do ERP (Silk).

O :class:`HelpAssistantService` decide, a partir do **perfil (role)** do usuário
e da **rota atual**, se o usuário pode receber ajuda de um módulo. Quando
permitido, carrega o manual Markdown correspondente (``docs/manual_erp/*.md``) e
o usa como contexto para a API de IA.

A trava de segurança (RBAC) é central: um usuário sem acesso ao financeiro, por
exemplo, recebe uma mensagem educada de bloqueio — nunca o conteúdo do módulo.
"""

import json
import logging
import urllib.error
import urllib.request
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)


class HelpAssistantService:
    """Assistente de ajuda do ERP com controle de acesso por role."""

    #: Módulo -> arquivo de manual (relativo a ``BASE_DIR``).
    MANUAIS = {
        "produtos": "docs/manual_erp/01_produtos_skus.md",
        "pedidos": "docs/manual_erp/02_pedidos_vendas.md",
        "financeiro": "docs/manual_erp/03_financeiro_caixa.md",
        "permissoes": "docs/manual_erp/04_permissoes_roles.md",
    }

    #: Nome amigável de cada módulo (usado nas mensagens).
    MODULO_NOMES = {
        "produtos": "Produtos e SKUs",
        "pedidos": "Pedidos e Vendas",
        "financeiro": "Financeiro",
        "permissoes": "Permissões",
    }

    #: Rota (prefixo) -> módulo. A ordem importa (prefixo mais específico antes).
    ROTAS = (
        ("/admin/financeiro/", "financeiro"),
        ("/admin/tenants/", "permissoes"),
        ("/admin/usuarios/", "permissoes"),
        ("/admin/auth/", "permissoes"),
        ("/admin/clientes/", "pedidos"),
        ("/admin/pedidos/", "pedidos"),
        ("/admin/produtos/", "produtos"),
    )

    #: Módulo -> roles com acesso. Superusuário do Django sempre acessa.
    MODULO_ROLES = {
        "produtos": {"SUPERADMIN", "GERENTE", "VENDAS", "COMPRAS", "AUDITOR"},
        "pedidos": {"SUPERADMIN", "GERENTE", "VENDAS", "COMPRAS", "AUDITOR"},
        "financeiro": {"SUPERADMIN", "GERENTE", "FINANCEIRO", "AUDITOR"},
        "permissoes": {"SUPERADMIN", "GERENTE", "AUDITOR"},
    }

    #: Palavras-chave que denunciam uma tentativa de acessar outro módulo
    #: mesmo estando em uma tela permitida (ex.: VENDAS perguntando de caixa).
    PALAVRAS_CHAVE = {
        "financeiro": (
            "conta a pagar",
            "contas a pagar",
            "conta a receber",
            "contas a receber",
            "caixa diário",
            "caixa diario",
            "fluxo de caixa",
            "movimentação de caixa",
            "movimentacao de caixa",
            "módulo financeiro",
            "modulo financeiro",
            "financeiro",
            "saldo do caixa",
            "faturamento",
        ),
        "permissoes": (
            "permissão",
            "permissoes",
            "permissões",
            "role",
            "roles",
            "usuário do sistema",
            "usuario do sistema",
        ),
    }

    SYSTEM_PROMPT = (
        "Você é o Silk, o guaxinim assistente do ERP BC Modas (confecção e "
        "estamparia). Responda em português do Brasil, de forma curta, objetiva "
        "e amigável. Use SOMENTE o contexto do manual fornecido e nunca invente "
        "dados, valores ou telas que não estejam no contexto."
    )

    def __init__(self, user, current_path=""):
        self.user = user
        self.current_path = (current_path or "").strip()

    # ── Identidade / papel ───────────────────────────────────────────────────
    @property
    def role(self):
        return getattr(self.user, "role", None)

    @property
    def is_super(self):
        return bool(getattr(self.user, "is_superuser", False))

    @property
    def role_display(self):
        try:
            return self.user.get_role_display()
        except Exception:  # pragma: no cover - usuário sem o método
            return self.role or "Usuário"

    # ── Mapeamentos ──────────────────────────────────────────────────────────
    def modulo_da_rota(self, path=None):
        """Retorna o módulo correspondente ao prefixo da rota informada."""
        path = path or self.current_path
        for prefixo, modulo in self.ROTAS:
            if path.startswith(prefixo):
                return modulo
        return None

    def modulo_da_pergunta(self, pergunta):
        """Detecta se a pergunta menciona um módulo restrito."""
        texto = (pergunta or "").lower()
        for modulo, palavras in self.PALAVRAS_CHAVE.items():
            if any(palavra in texto for palavra in palavras):
                return modulo
        return None

    def pode_acessar(self, modulo):
        """Indica se o usuário pode receber ajuda do módulo informado."""
        if modulo is None or self.is_super:
            return True
        if modulo == "permissoes" and self.is_super:
            return True
        roles = self.MODULO_ROLES.get(modulo)
        if not roles:
            return True
        return self.role in roles

    def carregar_manual(self, modulo):
        """Lê o conteúdo do manual Markdown do módulo (ou string vazia)."""
        if not modulo or modulo not in self.MANUAIS:
            return ""
        caminho = Path(settings.BASE_DIR) / self.MANUAIS[modulo]
        try:
            return caminho.read_text(encoding="utf-8")
        except OSError:
            logger.warning("Manual do Silk não encontrado: %s", caminho)
            return ""

    # ── Execução ─────────────────────────────────────────────────────────────
    def responder(self, pergunta):
        """Gera a resposta do Silk (ou o bloqueio por permissão).

        Retorna um dicionário serializável com ``resposta``, ``bloqueado``,
        ``modulo`` e ``fonte``.
        """
        pergunta = (pergunta or "").strip()

        # 1) Trava por rota atual.
        modulo_rota = self.modulo_da_rota()
        if modulo_rota and not self.pode_acessar(modulo_rota):
            return self._bloqueio(modulo_rota)

        # 2) Trava por conteúdo da pergunta (outro módulo restrito).
        modulo_pergunta = self.modulo_da_pergunta(pergunta)
        if modulo_pergunta and not self.pode_acessar(modulo_pergunta):
            return self._bloqueio(modulo_pergunta)

        modulo = modulo_rota or modulo_pergunta
        contexto = self.carregar_manual(modulo)
        prompt = self._montar_prompt(pergunta, contexto, modulo)
        resposta, fonte = self._gerar_resposta(prompt, contexto, modulo)
        return {
            "resposta": resposta,
            "bloqueado": False,
            "modulo": modulo,
            "fonte": fonte,
        }

    def _bloqueio(self, modulo):
        nome = self.MODULO_NOMES.get(modulo, modulo or "restrito").lower()
        mensagem = (
            f"Sua role {self.role_display} não possui acesso às informações do "
            f"módulo {nome}. Se precisar, solicite acesso a um gerente."
        )
        return {
            "resposta": mensagem,
            "bloqueado": True,
            "modulo": modulo,
            "fonte": None,
        }

    def _montar_prompt(self, pergunta, contexto, modulo):
        nome = self.MODULO_NOMES.get(modulo, "Geral")
        partes = [self.SYSTEM_PROMPT]
        if contexto:
            partes.append(f"Manual do módulo {nome}:\n{contexto}")
        partes.append(
            f"Pergunta do usuário ({self.role_display}): {pergunta}\n\n"
            "Responda com base no manual acima."
        )
        return "\n\n".join(partes)

    def _gerar_resposta(self, prompt, contexto, modulo):
        """Consulta a IA (se configurada) ou devolve um fallback com o manual."""
        api_key = getattr(settings, "SILK_AI_API_KEY", "") or ""
        if not api_key:
            return self._fallback(contexto, modulo), None
        try:
            return self._chamar_ia(prompt), modulo
        except Exception:  # pragma: no cover - depende de rede externa
            logger.exception("Falha ao consultar a API de IA do Silk")
            return self._fallback(contexto, modulo), None

    #: Endpoint compatível com a API OpenAI do Google Gemini. O caminho
    #: ``/chat/completions`` é acrescentado ao final.
    BASE_URL_PADRAO = "https://generativelanguage.googleapis.com/v1beta/openai"
    MODELO_PADRAO = "gemini-1.5-flash"

    def _chamar_ia(self, prompt):
        base_url = getattr(
            settings, "SILK_AI_BASE_URL", self.BASE_URL_PADRAO
        ).rstrip("/")
        modelo = getattr(settings, "SILK_AI_MODEL", self.MODELO_PADRAO)
        payload = {
            "model": modelo,
            "temperature": 0.2,
            "messages": [{"role": "user", "content": prompt}],
        }
        # O Gemini expõe um endpoint compatível com a API OpenAI e autentica
        # via cabeçalho "Authorization: Bearer <API_KEY>".
        requisicao = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {settings.SILK_AI_API_KEY}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        timeout = getattr(settings, "SILK_AI_TIMEOUT", 20)
        with urllib.request.urlopen(requisicao, timeout=timeout) as resposta:
            dados = json.loads(resposta.read().decode("utf-8"))
        return dados["choices"][0]["message"]["content"].strip()

    def _fallback(self, contexto, modulo):
        nome = self.MODULO_NOMES.get(modulo)
        trecho = self._trecho(contexto)
        if trecho:
            return (
                f"Não consegui consultar a IA agora, mas separei este trecho do "
                f"manual de {nome}:\n\n{trecho}\n\n"
                "Para respostas geradas por IA, configure a variável "
                "SILK_AI_API_KEY."
            )
        return (
            "Não consegui consultar a IA agora e não encontrei um manual "
            "específico para esta tela. Descreva sua dúvida com mais detalhes "
            "ou fale com um gerente."
        )

    @staticmethod
    def _trecho(contexto, limite=900):
        texto = (contexto or "").strip()
        if len(texto) <= limite:
            return texto
        recorte = texto[:limite]
        corte = recorte.rfind("\n")
        if corte > 200:
            recorte = recorte[:corte]
        return recorte.rstrip() + "…"
