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
import re
import unicodedata
import urllib.error
import urllib.parse
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
        "clientes": "docs/manual_erp/05_clientes.md",
    }

    #: Nome amigável de cada módulo (usado nas mensagens).
    MODULO_NOMES = {
        "produtos": "Produtos e SKUs",
        "pedidos": "Pedidos e Vendas",
        "financeiro": "Financeiro",
        "permissoes": "Permissões",
        "clientes": "Clientes",
    }

    #: Rota (prefixo) -> módulo. A ordem importa (prefixo mais específico antes).
    ROTAS = (
        ("/admin/financeiro/", "financeiro"),
        ("/admin/tenants/", "permissoes"),
        ("/admin/usuarios/", "permissoes"),
        ("/admin/auth/", "permissoes"),
        ("/admin/clientes/", "clientes"),
        ("/admin/pedidos/", "pedidos"),
        ("/admin/produtos/", "produtos"),
    )

    #: Módulo -> roles com acesso. Superusuário do Django sempre acessa.
    MODULO_ROLES = {
        "produtos": {"SUPERADMIN", "GERENTE", "VENDAS", "COMPRAS", "AUDITOR"},
        "pedidos": {"SUPERADMIN", "GERENTE", "VENDAS", "COMPRAS", "AUDITOR"},
        "financeiro": {"SUPERADMIN", "GERENTE", "FINANCEIRO", "AUDITOR"},
        "permissoes": {"SUPERADMIN", "GERENTE", "AUDITOR"},
        "clientes": {"SUPERADMIN", "GERENTE", "VENDAS", "COMPRAS", "AUDITOR"},
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

    #: Saudação devolvida quando o usuário apenas cumprimenta o assistente.
    SAUDACAO_RESPOSTA = "Olá! Como posso te ajudar com o ERP hoje?"

    #: Perguntas guiadas (Modo Guiado / FAQ Interativo) — chave -> frases
    #: canônicas (já normalizadas) que acionam uma resposta curta sem IA.
    GUIAS = {
        "visao_geral": {
            "o que e esta tela",
            "o que e essa tela",
        },
        "resumo": {
            "resumo deste ecra",
        },
        "alertas": {
            "como ler os alertas",
        },
        "graficos": {
            "como os graficos sao atualizados",
            "como os graficos atualizam",
        },
        "cadastrar": {
            "como cadastrar",
            "como cadastrar um registro",
            "como crio um registro",
            "como criar um pedido",
            "como registrar contas",
            "como definir acesso",
        },
        "regras": {
            "regras de negocio",
            "quais as regras",
        },
        "sku": {
            "o que e um sku",
        },
        "precos": {
            "diferenca de preco varejo atacado",
            "qual a diferenca entre varejo e atacado",
        },
        "status_pedido": {
            "fluxo de status",
        },
        "trava_financeira": {
            "o que e a trava financeira",
        },
        "cancelar_pedido": {
            "como cancelar um pedido",
        },
        "associar_cliente": {
            "como associar um cliente",
        },
        "pf_pj": {
            "pessoa fisica vs juridica",
            "diferenca entre pf e pj",
        },
        "historico_cliente": {
            "onde vejo o historico",
        },
        "inativar_cliente": {
            "inativar cliente",
            "como inativar um cliente",
        },
        "baixa_conta": {
            "como dar baixa numa conta",
            "como dar baixa em uma conta",
        },
        "caixa_pedidos": {
            "o que e o caixa de pedidos",
        },
        "estorno": {
            "estorno de valores",
            "como estornar um valor",
        },
        "role": {
            "o que e uma role",
        },
    }

    #: Respostas curtas do FAQ Interativo por módulo (fallback "geral").
    RESPOSTAS_CURTAS = {
        "geral": {
            "visao_geral": (
                "Esta é a visão geral do ERP BC Modas. Use o menu lateral para "
                "navegar entre os módulos Produtos, Pedidos, Clientes, "
                "Financeiro e Usuários."
            ),
            "resumo": (
                "Aqui você vê os indicadores principais da fábrica: pedidos do "
                "dia, faturamento no mês, contas a pagar próximas, pedidos "
                "retidos e SKUs em alerta de estoque."
            ),
            "alertas": (
                "Os cartões sinalizam situações que pedem atenção: Pedidos "
                "Retidos (aguardando liberação financeira) e SKUs em Alerta de "
                "Estoque (saldo menor ou igual a 5 peças), entre outros."
            ),
            "graficos": (
                "Os indicadores refletem os dados salvos mais recentemente e são "
                "atualizados a cada carregamento da página. Atualize a tela "
                "após registrar movimentações para ver os novos valores."
            ),
            "cadastrar": (
                "Depende da tela: abra o módulo desejado pelo menu lateral e "
                "clique no botão Adicionar para criar um novo registro."
            ),
            "regras": (
                "As regras específicas estão descritas no manual de cada módulo. "
                "Abra a tela desejada e escolha uma pergunta, ou fale com um "
                "gerente."
            ),
        },
        "produtos": {
            "visao_geral": (
                "Esta tela pertence ao módulo Produtos e SKUs: Categorias organizam "
                "o catálogo, Modelos são os produtos 'pai' com preços de varejo e "
                "atacado, e a grade de SKUs controla cor, tamanho e estoque."
            ),
            "cadastrar": (
                "Vá em Produtos → Modelos → Adicionar. Preencha nome, marca e "
                "categoria, defina os preços (varejo/atacado) e a quantidade mínima "
                "de atacado, salve e adicione os SKUs (cor + tamanho) com estoque."
            ),
            "regras": (
                "Estoque é controlado por SKU (variação), não pelo modelo; o par "
                "Modelo + Cor + Tamanho é único; e o preço de atacado entra "
                "automaticamente ao atingir a quantidade mínima configurada."
            ),
            "sku": (
                "SKU é a variação de um modelo: uma combinação única de "
                "Modelo + Cor + Tamanho (ex.: Camiseta penteada branca tamanho M). "
                "É no SKU que o estoque é controlado e dado baixa nas vendas."
            ),
            "precos": (
                "O Preço Varejo é o valor da peça avulsa. O Preço Atacado passa a "
                "valer quando o pedido atinge a Qtd. Mínima Atacado do modelo — o "
                "sistema aplica o atacado automaticamente nesse caso."
            ),
        },
        "pedidos": {
            "visao_geral": (
                "Esta tela pertence ao módulo Pedidos e Vendas, que cobre todo o "
                "ciclo de venda: criação do pedido, itens, vínculo com o cliente e "
                "o fluxo de status até a entrega."
            ),
            "cadastrar": (
                "Vá em Pedidos → Adicionar, selecione o cliente (ou preencha nome, "
                "documento e WhatsApp), escolha forma de pagamento e tipo de "
                "entrega, adicione os itens com quantidade e preço e confira o "
                "valor total antes de salvar."
            ),
            "regras": (
                "Principal regra: enquanto o pagamento não for confirmado "
                "(Pago/Liberado ou Faturado Atacado, ou conta a receber "
                "Paga/Faturada), o pedido não avança para produção, separação, "
                "entrega ou conclusão — é a trava financeira."
            ),
            "status_pedido": (
                "O fluxo é: Aguardando Pagamento → Pago/Liberado → Em Produção → "
                "Em Separação → Pronto p/ Entrega → Enviado → Entregue → "
                "Concluído (ou Cancelado). O pedido só avança para produção após "
                "o pagamento ser confirmado."
            ),
            "trava_financeira": (
                "É a regra que impede o pedido de avançar para produção, "
                "separação, entrega ou conclusão enquanto o pagamento não estiver "
                "confirmado — como Pago/Liberado, Faturado Atacado ou uma conta a "
                "receber Paga/Faturada."
            ),
            "cancelar_pedido": (
                "Abra o pedido, altere o status para Cancelado e salve. Pedidos "
                "cancelados não geram movimentação financeira."
            ),
            "associar_cliente": (
                "No pedido, selecione o cliente existente no campo Cliente ou, se "
                "ainda não houver cadastro, preencha manualmente nome, documento "
                "e WhatsApp no próprio pedido."
            ),
        },
        "clientes": {
            "visao_geral": (
                "Esta tela pertence ao módulo de Clientes: reúne os compradores "
                "(Pessoa Física ou Jurídica) com seus contatos e endereço, usados "
                "nos pedidos e na auditoria (LGPD)."
            ),
            "cadastrar": (
                "Vá em Clientes → Adicionar. Preencha Nome/Razão Social, Tipo de "
                "Pessoa (PF ou PJ), CPF/CNPJ, WhatsApp, E-mail e endereço "
                "(opcional). Mantenha Ativo marcado para liberar o cliente no dia "
                "a dia."
            ),
            "regras": (
                "Cada cliente é vinculado aos pedidos para auditoria (LGPD). PF "
                "usa CPF e PJ usa CNPJ; inativar o cliente não apaga o cadastro, "
                "apenas o remove do uso do dia a dia."
            ),
            "pf_pj": (
                "Pessoa Física (PF) é o cliente pessoa comum e usa CPF; Pessoa "
                "Jurídica (PJ) é uma empresa e usa CNPJ. O tipo escolhido define "
                "qual documento é informado no cadastro."
            ),
            "historico_cliente": (
                "O histórico fica registrado nos pedidos vinculados ao cliente e "
                "nas datas de criação/atualização do cadastro, visíveis na aba de "
                "Auditoria."
            ),
            "inativar_cliente": (
                "Abra o cliente, desmarque o campo Ativo e salve. O cliente "
                "inativo deixa de ser usado no dia a dia, mas o cadastro e o "
                "histórico são mantidos."
            ),
        },
        "financeiro": {
            "visao_geral": (
                "Esta tela pertence ao módulo Financeiro e Caixa, que controla "
                "Contas a Receber, Contas a Pagar e as Movimentações de Caixa. O "
                "acesso é restrito a SUPERADMIN, GERENTE, FINANCEIRO e AUDITOR."
            ),
            "cadastrar": (
                "Registre recebimentos nas Contas a Receber (ou confirme em Caixa "
                "de Pedidos), despesas nas Contas a Pagar e faça os lançamentos no "
                "Caixa Diário e nas Movimentações para fechar o dia."
            ),
            "regras": (
                "Marcar uma conta a receber como Recebida gera entrada de caixa; "
                "marcar conta a pagar como Paga gera saída; há um único caixa por "
                "empresa e data; e contas Pendentes mantêm a trava financeira."
            ),
            "baixa_conta": (
                "Abra a conta e altere o status para Recebida (contas a receber) "
                "ou Paga (contas a pagar). Isso gera automaticamente a entrada ou "
                "saída correspondente no caixa."
            ),
            "caixa_pedidos": (
                "É a área das Contas a Receber vinculadas a pedidos: mostra o que "
                "cada pedido deve e contas com status Pago ou Faturado liberam o "
                "pedido para produção e expedição."
            ),
            "estorno": (
                "Não há um botão único de estorno: cancele ou ajuste a conta "
                "original e registre a movimentação inversa no caixa, mantendo o "
                "histórico auditável."
            ),
        },
        "permissoes": {
            "visao_geral": (
                "Esta tela pertence ao módulo de Permissões e Roles (RBAC). O "
                "acesso é controlado por perfil — SUPERADMIN, GERENTE, COMPRAS, "
                "VENDAS, FINANCEIRO e AUDITOR — e cada perfil enxerga apenas o "
                "que pode ver e editar."
            ),
            "cadastrar": (
                "Cadastre o usuário escolhendo a role adequada à função dele. "
                "Conceda o menor privilégio necessário e use AUDITOR para "
                "auditorias somente leitura."
            ),
            "regras": (
                "FINANCEIRO enxerga apenas o bloco Financeiro; AUDITOR é somente "
                "leitura; o superusuário do Django sempre tem acesso total; e o "
                "Silk bloqueia ajuda de módulos sem permissão da role."
            ),
            "role": (
                "Role é o perfil de acesso do usuário no ERP. Os disponíveis são "
                "SUPERADMIN, GERENTE, COMPRAS, VENDAS, FINANCEIRO e AUDITOR; cada "
                "role enxerga e edita apenas o que o perfil permite."
            ),
        },
    }

    #: Cumprimentos simples tratados direto no código (sem acionar a IA).
    SAUDACOES = {
        "oi",
        "ola",
        "opa",
        "hey",
        "hello",
        "hi",
        "bom dia",
        "boa tarde",
        "boa noite",
        "e ai",
        "eai",
        "tudo bem",
        "tudo bom",
        "tudo certo",
        "oi tudo bem",
        "ola tudo bem",
        "bom dia tudo bem",
        "boa tarde tudo bem",
        "boa noite tudo bem",
    }

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

    # ── Saudações ────────────────────────────────────────────────────────────
    @staticmethod
    def _normalizar(texto):
        """Minúsculas, sem acentos e sem pontuação, para casar frases."""
        texto = (texto or "").strip().lower()
        texto = "".join(
            caractere
            for caractere in unicodedata.normalize("NFD", texto)
            if unicodedata.category(caractere) != "Mn"
        )
        texto = re.sub(r"[!?.,;:/]+", " ", texto)
        return re.sub(r"\s+", " ", texto).strip()

    def e_saudacao(self, pergunta):
        """Detecta cumprimentos simples (ex.: "oi", "bom dia")."""
        return self._normalizar(pergunta) in self.SAUDACOES

    # ── Modo Guiado ──────────────────────────────────────────────────────────
    def _pergunta_guiada(self, pergunta):
        """Chave da pergunta guiada correspondente, ou ``None`` para texto livre."""
        normal = self._normalizar(pergunta)
        for chave, frases in self.GUIAS.items():
            if normal in frases:
                return chave
        return None

    def _resposta_curta(self, chave, modulo):
        """Resposta curta e direta do FAQ Interativo para o módulo atual."""
        respostas = self.RESPOSTAS_CURTAS.get(modulo) or self.RESPOSTAS_CURTAS["geral"]
        return (
            respostas.get(chave)
            or self.RESPOSTAS_CURTAS["geral"].get(chave)
            or "Não tenho uma resposta pronta para esta tela. Fale com um gerente."
        )

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

        # 0) Saudações simples: resposta imediata, sem acionar a IA nem fallback.
        if self.e_saudacao(pergunta):
            return {
                "resposta": self.SAUDACAO_RESPOSTA,
                "bloqueado": False,
                "modulo": None,
                "fonte": None,
            }

        # 1) Trava por rota atual.
        modulo_rota = self.modulo_da_rota()
        if modulo_rota and not self.pode_acessar(modulo_rota):
            return self._bloqueio(modulo_rota)

        # 2) Trava por conteúdo da pergunta (outro módulo restrito).
        modulo_pergunta = self.modulo_da_pergunta(pergunta)
        if modulo_pergunta and not self.pode_acessar(modulo_pergunta):
            return self._bloqueio(modulo_pergunta)

        modulo = modulo_rota or modulo_pergunta

        # 3) Modo Guiado: respostas curtas para as perguntas padrão, sem IA.
        chave = self._pergunta_guiada(pergunta)
        if chave:
            return {
                "resposta": self._resposta_curta(chave, modulo),
                "bloqueado": False,
                "modulo": modulo,
                "fonte": None,
            }

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
        # via cabeçalho "Authorization: Bearer <API_KEY>". Enviamos também a
        # chave no parâmetro de URL (?key=<API_KEY>) para compatibilidade total
        # com as chaves do Google AI Studio.
        api_key = settings.SILK_AI_API_KEY
        query = urllib.parse.urlencode({"key": api_key})
        requisicao = urllib.request.Request(
            f"{base_url}/chat/completions?{query}",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
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
                f"Aqui está um trecho do manual de {nome} que pode ajudar:"
                f"\n\n{trecho}"
            )
        return (
            "Não encontrei um manual específico para esta tela. Descreva sua "
            "dúvida com mais detalhes ou fale com um gerente."
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
