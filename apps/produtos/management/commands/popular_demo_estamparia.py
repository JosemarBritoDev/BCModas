"""Popula o ERP com dados de demonstração hiper-realistas de Estamparia/Serigrafia.

Cria, vinculados à empresa principal (``Empresa.obter_fabrica()`` ou a primeira
cadastrada):

* 7 categorias comerciais;
* 20 modelos (camisetas, moletons, uniformes, ecobags, canecas e bonés) com
  preços de varejo/atacado;
* grade de SKUs (2 a 3 por modelo) variando tamanho e cores reais (com hex);
* 6 clientes de demonstração (Pessoa Física e Jurídica) com CPF/CNPJ válidos;
* 7 pedidos com status variados (Pendente, Faturado, Entregue) e seus itens;
* Financeiro: parcelas em Contas a Receber (pedidos faturados), Contas a Pagar
  de fornecedores reais do ramo e movimentações de Caixa (entradas e saídas).

O comando é idempotente (usa ``get_or_create``/``update_or_create`` com chaves
naturais e um marcador em ``Pedido.versao_termos``) e não duplica registros ao
ser executado repetidamente.

Uso:
    python manage.py popular_demo_estamparia
    python manage.py popular_demo_estamparia --clean
"""

import hashlib
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.clientes.models import Cliente
from apps.financeiro.models import CaixaMovimentacao, ContaPagar, ContaReceber
from apps.financeiro.services import obter_caixa_do_dia
from apps.pedidos.models import ItemPedido, Pedido
from apps.produtos.models import Categoria, Modelo, SKU
from apps.tenants.models import Empresa

# Marcador que identifica os pedidos de demonstração (permite limpeza segura).
TAG_DEMO = "demo-estamparia"
VERSAO_TERMOS_DEMO = "Demo v1"

# ── Paleta de cores reais (nome, hexadecimal) ────────────────────────────────
PRETO = ("Preto", "#111111")
BRANCO = ("Branco", "#FFFFFF")
OFF_WHITE = ("Off White", "#F5F5F4")
CINZA_MESCLA = ("Cinza Mescla", "#9CA3AF")
CINZA_CHUMBO = ("Cinza Chumbo", "#4B5563")
AZUL_MARINHO = ("Azul Marinho", "#1E3A8A")
AZUL_ROYAL = ("Azul Royal", "#1D4ED8")
AZUL_CELESTE = ("Azul Celeste", "#7DD3FC")
VERDE_MILITAR = ("Verde Militar", "#3F6212")
VERDE_BANDEIRA = ("Verde Bandeira", "#166534")
VINHO = ("Vinho", "#7F1D1D")
VERMELHO = ("Vermelho", "#DC2626")
AMARELO_OURO = ("Amarelo Ouro", "#EAB308")
ROSA = ("Rosa", "#EC4899")
LARANJA = ("Laranja", "#EA580C")
GRAFITE = ("Grafite", "#374151")
BEGE = ("Bege", "#D6C7A1")
CARAMELO = ("Caramelo", "#B45309")

ROUPAS = ["P", "M", "G", "GG", "XG"]
TRES_TAMANHOS = ["P", "M", "G"]

# ── Categorias (slug, nome, ordem) ───────────────────────────────────────────
CATEGORIAS = [
    ("camisetas-lisas", "Camisetas Lisas", 0),
    ("moletons", "Moletons", 1),
    ("uniformes-corporativos", "Uniformes Corporativos", 2),
    ("ecobags", "Ecobags", 3),
    ("canecas", "Canecas", 4),
    ("bones", "Bonés", 5),
    ("estampas-personalizadas", "Estampas Personalizadas", 6),
]

# ── Produtos/Modelos (20) ────────────────────────────────────────────────────
PRODUTOS = [
    # Camisetas Lisas
    {
        "nome": "Camiseta Algodão Penteado 30.1",
        "categoria": "camisetas-lisas",
        "marca": "BC Estamparia",
        "preco_varejo": "49.90",
        "preco_atacado": "29.90",
        "qtd_minima_atacado": 10,
        "composicao": "100% algodão penteado fio 30.1",
        "gramatura": "175g/m²",
        "descricao": "Camiseta unissex de algodão penteado, ideal para estamparia em DTF e silk.",
        "cores": [PRETO, BRANCO, CINZA_MESCLA, AZUL_MARINHO],
        "tamanhos": ROUPAS,
        "estoque_base": 180,
    },
    {
        "nome": "Camiseta Oversized DTF",
        "categoria": "camisetas-lisas",
        "marca": "BC Estamparia",
        "lancamento": True,
        "preco_varejo": "79.90",
        "preco_atacado": "49.90",
        "qtd_minima_atacado": 8,
        "composicao": "100% algodão penteado",
        "gramatura": "185g/m²",
        "descricao": "Camiseta oversized com caimento amplo e gola reforçada, perfeita para DTF.",
        "cores": [PRETO, OFF_WHITE, VERDE_MILITAR, VINHO],
        "tamanhos": ROUPAS,
        "estoque_base": 140,
    },
    {
        "nome": "Camiseta Baby Look Silk",
        "categoria": "camisetas-lisas",
        "marca": "BC Estamparia",
        "preco_varejo": "59.90",
        "preco_atacado": "36.90",
        "qtd_minima_atacado": 10,
        "composicao": "100% algodão penteado",
        "gramatura": "170g/m²",
        "descricao": "Baby look feminina com modelagem ajustada, ótima para silkscreen.",
        "cores": [BRANCO, ROSA, PRETO, AMARELO_OURO],
        "tamanhos": TRES_TAMANHOS,
        "estoque_base": 120,
    },
    {
        "nome": "Camiseta Manga Longa DTF",
        "categoria": "camisetas-lisas",
        "marca": "BC Estamparia",
        "preco_varejo": "69.90",
        "preco_atacado": "44.90",
        "qtd_minima_atacado": 8,
        "composicao": "100% algodão",
        "gramatura": "180g/m²",
        "descricao": "Camiseta manga longa com punho, indicada para uniformes e estampas em DTF.",
        "cores": [PRETO, BRANCO, GRAFITE],
        "tamanhos": ROUPAS,
        "estoque_base": 90,
    },
    {
        "nome": "Camiseta Dry Fit Sublimada",
        "categoria": "camisetas-lisas",
        "marca": "BC Fit",
        "preco_varejo": "64.90",
        "preco_atacado": "39.90",
        "qtd_minima_atacado": 10,
        "composicao": "100% poliéster",
        "gramatura": "160g/m²",
        "descricao": "Camiseta esportiva em dry fit para sublimação total, secagem rápida.",
        "cores": [VERDE_BANDEIRA, AZUL_ROYAL, VERMELHO, PRETO],
        "tamanhos": ROUPAS,
        "estoque_base": 110,
    },
    # Moletons
    {
        "nome": "Moletom Canguru DTF",
        "categoria": "moletons",
        "marca": "BC Estamparia",
        "lancamento": True,
        "preco_varejo": "159.90",
        "preco_atacado": "109.90",
        "qtd_minima_atacado": 6,
        "composicao": "80% algodão, 20% poliéster",
        "gramatura": "330g/m²",
        "descricao": "Moletom com capuz, bolso canguru e interior flanelado, ideal para DTF.",
        "cores": [PRETO, GRAFITE, VERDE_MILITAR, VINHO],
        "tamanhos": ROUPAS,
        "estoque_base": 70,
    },
    {
        "nome": "Moletom Gola Careca Silkscreen",
        "categoria": "moletons",
        "marca": "BC Estamparia",
        "preco_varejo": "129.90",
        "preco_atacado": "89.90",
        "qtd_minima_atacado": 6,
        "composicao": "90% algodão, 10% poliéster",
        "gramatura": "300g/m²",
        "descricao": "Moletom gola careca com punho e barra em ribana, ótimo para silk.",
        "cores": [PRETO, CINZA_MESCLA, AZUL_MARINHO],
        "tamanhos": ROUPAS,
        "estoque_base": 60,
    },
    {
        "nome": "Jaqueta Corta-Vento Personalizada",
        "categoria": "moletons",
        "marca": "BC Estamparia",
        "preco_varejo": "149.90",
        "preco_atacado": "99.90",
        "qtd_minima_atacado": 6,
        "composicao": "Poliamida com forro em tafetá",
        "gramatura": "Média",
        "descricao": "Jaqueta corta-vento com capuz e zíper, para uniformes e brindes.",
        "cores": [PRETO, AZUL_ROYAL, LARANJA],
        "tamanhos": ROUPAS,
        "estoque_base": 45,
    },
    # Uniformes Corporativos
    {
        "nome": "Uniforme Social Bordado",
        "categoria": "uniformes-corporativos",
        "marca": "BC Corporativo",
        "preco_varejo": "139.90",
        "preco_atacado": "94.90",
        "qtd_minima_atacado": 10,
        "composicao": "65% algodão, 35% poliéster",
        "gramatura": "Média",
        "descricao": "Conjunto social com camisa e calça para equipes, personalizado com bordado.",
        "cores": [AZUL_MARINHO, PRETO, GRAFITE],
        "tamanhos": ROUPAS,
        "estoque_base": 80,
    },
    {
        "nome": "Camisa Polo Piquet Bordada",
        "categoria": "uniformes-corporativos",
        "marca": "BC Corporativo",
        "preco_varejo": "119.90",
        "preco_atacado": "79.90",
        "qtd_minima_atacado": 10,
        "composicao": "100% algodão piquet",
        "gramatura": "Piquet",
        "descricao": "Polo em piquet com gola ribana e logo bordado, padrão corporativo.",
        "cores": [PRETO, BRANCO, AZUL_MARINHO, VERDE_BANDEIRA],
        "tamanhos": ROUPAS,
        "estoque_base": 95,
    },
    {
        "nome": "Jaleco Profissional Bordado",
        "categoria": "uniformes-corporativos",
        "marca": "BC Corporativo",
        "preco_varejo": "129.90",
        "preco_atacado": "89.90",
        "qtd_minima_atacado": 8,
        "composicao": "67% poliéster, 33% algodão",
        "gramatura": "Média",
        "descricao": "Jaleco profissional com bolsos e bordado personalizado da empresa.",
        "cores": [BRANCO, AZUL_CELESTE],
        "tamanhos": ROUPAS,
        "estoque_base": 50,
    },
    {
        "nome": "Avental Personalizado",
        "categoria": "uniformes-corporativos",
        "marca": "BC Corporativo",
        "preco_varejo": "89.90",
        "preco_atacado": "59.90",
        "qtd_minima_atacado": 12,
        "composicao": "100% algodão",
        "gramatura": "Alta",
        "descricao": "Avental de brim resistente com alças reguláveis e estampa/silk do negócio.",
        "cores": [BEGE, CARAMELO, PRETO],
        "tamanhos": TRES_TAMANHOS,
        "estoque_base": 65,
    },
    # Ecobags
    {
        "nome": "Ecobag Algodão Cru",
        "categoria": "ecobags",
        "marca": "BC Eco",
        "preco_varejo": "39.90",
        "preco_atacado": "24.90",
        "qtd_minima_atacado": 20,
        "composicao": "100% algodão cru",
        "gramatura": "140g/m²",
        "descricao": "Ecobag de algodão cru com alças reforçadas, perfeita para silk e DTF.",
        "cores": [BEGE, OFF_WHITE, PRETO],
        "tamanhos": TRES_TAMANHOS,
        "estoque_base": 200,
    },
    {
        "nome": "Ecobag Poliéster Personalizada",
        "categoria": "ecobags",
        "marca": "BC Eco",
        "preco_varejo": "34.90",
        "preco_atacado": "19.90",
        "qtd_minima_atacado": 20,
        "composicao": "100% poliéster",
        "gramatura": "Média",
        "descricao": "Ecobag em poliéster com fechamento por zíper e estampa sublimática.",
        "cores": [PRETO, AZUL_ROYAL, ROSA, VERDE_BANDEIRA],
        "tamanhos": TRES_TAMANHOS,
        "estoque_base": 150,
    },
    # Canecas
    {
        "nome": "Caneca Cerâmica Branca",
        "categoria": "canecas",
        "marca": "BC Brindes",
        "preco_varejo": "29.90",
        "preco_atacado": "18.90",
        "qtd_minima_atacado": 24,
        "composicao": "Cerâmica esmaltada",
        "gramatura": "325ml",
        "descricao": "Caneca de cerâmica branca para sublimação, com alça reforçada.",
        "cores": [BRANCO],
        "tamanhos": ["P", "M", "G"],
        "estoque_base": 240,
    },
    {
        "nome": "Caneca Mágica Cabrocha",
        "categoria": "canecas",
        "marca": "BC Brindes",
        "lancamento": True,
        "preco_varejo": "39.90",
        "preco_atacado": "26.90",
        "qtd_minima_atacado": 24,
        "composicao": "Cerâmica com revestimento termossensível",
        "gramatura": "325ml",
        "descricao": "Caneca que revela a estampa com líquido quente, efeito mágico exclusivo.",
        "cores": [PRETO, BRANCO],
        "tamanhos": ["P", "M", "G"],
        "estoque_base": 160,
    },
    {
        "nome": "Caneca Porcelana 325ml",
        "categoria": "canecas",
        "marca": "BC Brindes",
        "preco_varejo": "34.90",
        "preco_atacado": "22.90",
        "qtd_minima_atacado": 24,
        "composicao": "Porcelana premium",
        "gramatura": "325ml",
        "descricao": "Caneca de porcelana com acabamento fino, ideal para brindes corporativos.",
        "cores": [BRANCO, AZUL_CELESTE],
        "tamanhos": ["P", "M", "G"],
        "estoque_base": 130,
    },
    # Bonés
    {
        "nome": "Boné Trucker Bordado",
        "categoria": "bones",
        "marca": "BC Brindes",
        "preco_varejo": "49.90",
        "preco_atacado": "32.90",
        "qtd_minima_atacado": 12,
        "composicao": "Frontal em algodão, traseira em tela",
        "gramatura": "Média",
        "descricao": "Boné trucker com aba curva e frontal para bordado personalizado.",
        "cores": [PRETO, BRANCO, AZUL_MARINHO, VERMELHO],
        "tamanhos": ["M", "G"],
        "estoque_base": 90,
    },
    {
        "nome": "Boné Aba Reta Silk",
        "categoria": "bones",
        "marca": "BC Brindes",
        "preco_varejo": "45.90",
        "preco_atacado": "29.90",
        "qtd_minima_atacado": 12,
        "composicao": "100% algodão",
        "gramatura": "Média",
        "descricao": "Boné de aba reta com fechamento snapback, indicado para silkscreen.",
        "cores": [PRETO, AMARELO_OURO, VERDE_BANDEIRA, LARANJA],
        "tamanhos": ["M", "G"],
        "estoque_base": 85,
    },
    {
        "nome": "Boné Dad Hat Bordado",
        "categoria": "bones",
        "marca": "BC Brindes",
        "preco_varejo": "54.90",
        "preco_atacado": "34.90",
        "qtd_minima_atacado": 12,
        "composicao": "100% algodão sarja",
        "gramatura": "Média",
        "descricao": "Dad hat com perfil baixo, lavado e bordado em relevo no frontal.",
        "cores": [BEGE, CINZA_CHUMBO, VINHO],
        "tamanhos": ["M", "G"],
        "estoque_base": 75,
    },
]

# ── Clientes (PF e PJ) com documentos válidos gerados no seed ────────────────
CLIENTES = [
    {
        "nome_razao_social": "Marcos Vinícius Andrade",
        "tipo_pessoa": "PF",
        "doc_base": "123456789",
        "email": "marcos.andrade@estamparia-demo.com.br",
        "whatsapp": "(11) 98877-1001",
        "cep": "03047-000",
        "endereco": "Rua do Comércio",
        "numero": "120",
        "bairro": "Brás",
        "cidade": "São Paulo",
        "estado": "SP",
    },
    {
        "nome_razao_social": "Juliana Ferreira Gomes",
        "tipo_pessoa": "PF",
        "doc_base": "321654987",
        "email": "juliana.gomes@estamparia-demo.com.br",
        "whatsapp": "(21) 99654-2002",
        "cep": "20511-000",
        "endereco": "Rua Voluntários da Pátria",
        "numero": "88",
        "bairro": "Botafogo",
        "cidade": "Rio de Janeiro",
        "estado": "RJ",
    },
    {
        "nome_razao_social": "Rafael Nogueira Prado",
        "tipo_pessoa": "PF",
        "doc_base": "456123789",
        "email": "rafael.prado@estamparia-demo.com.br",
        "whatsapp": "(31) 98123-3003",
        "cep": "30140-071",
        "endereco": "Rua dos Tupis",
        "numero": "450",
        "bairro": "Centro",
        "cidade": "Belo Horizonte",
        "estado": "MG",
    },
    {
        "nome_razao_social": "Camila Rodrigues Lopes",
        "tipo_pessoa": "PF",
        "doc_base": "789321654",
        "email": "camila.lopes@estamparia-demo.com.br",
        "whatsapp": "(41) 99222-4004",
        "cep": "80020-320",
        "endereco": "Rua XV de Novembro",
        "numero": "910",
        "bairro": "Centro",
        "cidade": "Curitiba",
        "estado": "PR",
    },
    {
        "nome_razao_social": "Confecções Estrela Ltda",
        "tipo_pessoa": "PJ",
        "doc_base": "123456780001",
        "email": "compras@confecoesestrela-demo.com.br",
        "whatsapp": "(11) 97766-5005",
        "cep": "07124-000",
        "endereco": "Avenida das Nações",
        "numero": "1500",
        "bairro": "Cumbica",
        "cidade": "Guarulhos",
        "estado": "SP",
    },
    {
        "nome_razao_social": "Academia Corpo Ativo ME",
        "tipo_pessoa": "PJ",
        "doc_base": "987654320001",
        "email": "contato@corpoativo-demo.com.br",
        "whatsapp": "(51) 98555-6006",
        "cep": "90570-020",
        "endereco": "Rua Mostardeiro",
        "numero": "300",
        "bairro": "Moinhos de Vento",
        "cidade": "Porto Alegre",
        "estado": "RS",
    },
]

# ── Pedidos de demonstração ──────────────────────────────────────────────────
# status: PENDENTE (aguardando pagamento), FATURADO (faturado atacado),
#         ENTREGUE (pago e entregue).
PEDIDOS = [
    {
        "cliente": 4,
        "status": "FATURADO",
        "forma": "PIX",
        "entrega": "ENTREGA",
        "parcelas": 3,
        "itens": [("Camiseta Algodão Penteado 30.1", 200), ("Camiseta Oversized DTF", 80)],
    },
    {
        "cliente": 5,
        "status": "FATURADO",
        "forma": "PIX",
        "entrega": "ENTREGA",
        "parcelas": 2,
        "itens": [("Camiseta Dry Fit Sublimada", 120), ("Boné Trucker Bordado", 60)],
    },
    {
        "cliente": 0,
        "status": "ENTREGUE",
        "forma": "PIX",
        "entrega": "RETIRADA_LOCAL",
        "itens": [("Camiseta Baby Look Silk", 5), ("Caneca Cerâmica Branca", 3)],
    },
    {
        "cliente": 1,
        "status": "PENDENTE",
        "forma": "PIX",
        "entrega": "RETIRADA_LOCAL",
        "itens": [("Ecobag Algodão Cru", 10)],
    },
    {
        "cliente": 2,
        "status": "ENTREGUE",
        "forma": "CREDITO",
        "entrega": "ENTREGA",
        "itens": [("Moletom Canguru DTF", 4), ("Boné Dad Hat Bordado", 2)],
    },
    {
        "cliente": 3,
        "status": "FATURADO",
        "forma": "PIX",
        "entrega": "ENTREGA",
        "parcelas": 2,
        "itens": [("Uniforme Social Bordado", 150)],
    },
    {
        "cliente": 4,
        "status": "ENTREGUE",
        "forma": "PIX",
        "entrega": "ENTREGA",
        "itens": [("Camisa Polo Piquet Bordada", 40), ("Avental Personalizado", 30)],
    },
]

# ── Contas a Pagar (fornecedor, categoria, descrição, valor, vencimento, pago) ─
CONTAS_PAGAR = [
    ("Fornecedor de Malha São Paulo", "MATERIA_PRIMA", "Compra de malha 100% algodão (500kg)", "8750.00", 7, True),
    ("Tintas Silk Color", "MATERIA_PRIMA", "Compra de tintas plastisol e emulsão", "2340.50", -3, False),
    ("Imobiliária Central", "OPERACIONAL", "Aluguel do galpão de estamparia", "4800.00", 5, True),
    ("Enel Distribuição", "OPERACIONAL", "Energia elétrica do galpão", "1260.80", -2, True),
    ("Simples Nacional", "IMPOSTOS", "DAS - Simples Nacional", "1980.00", 10, False),
]


def _gerar_cpf(base9):
    """Gera um CPF fictício com dígitos verificadores válidos a partir de 9 dígitos."""
    base9 = "".join(ch for ch in str(base9) if ch.isdigit())[:9].ljust(9, "7")

    def digito(numeros):
        soma = sum(int(n) * (len(numeros) + 1 - i) for i, n in enumerate(numeros))
        resto = soma % 11
        return "0" if resto < 2 else str(11 - resto)

    dv1 = digito(base9)
    dv2 = digito(base9 + dv1)
    return f"{base9[:3]}.{base9[3:6]}.{base9[6:9]}-{dv1}{dv2}"


def _gerar_cnpj(base12):
    """Gera um CNPJ fictício com dígitos verificadores válidos a partir de 12 dígitos."""
    base = "".join(ch for ch in str(base12) if ch.isdigit())[:12].ljust(12, "0")

    def digito(numeros, pesos):
        soma = sum(int(n) * p for n, p in zip(numeros, pesos))
        resto = soma % 11
        return "0" if resto < 2 else str(11 - resto)

    d1 = digito(base, [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    d2 = digito(base + d1, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    raw = base + d1 + d2
    return f"{raw[:2]}.{raw[2:5]}.{raw[5:8]}/{raw[8:12]}-{raw[12:]}"


class Command(BaseCommand):
    help = (
        "Popula o ERP com dados de demonstração de Estamparia/Serigrafia "
        "(categorias, produtos, SKUs, clientes, pedidos e financeiro). Idempotente."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--clean",
            action="store_true",
            help="Remove apenas os dados de demonstração, preservando usuários e migrações.",
        )

    def handle(self, *args, **options):
        empresa = Empresa.obter_fabrica() or Empresa.objects.order_by("pk").first()
        if empresa is None:
            raise CommandError(
                "Nenhuma empresa (fábrica) cadastrada. Cadastre os Dados da Confecção "
                "no admin antes de popular a demonstração."
            )

        if options["clean"]:
            self._limpar(empresa)
            return

        with transaction.atomic():
            categorias = self._criar_categorias(empresa)
            modelos = self._criar_produtos(empresa, categorias)
            clientes = self._criar_clientes(empresa)
            pedidos = self._criar_pedidos(empresa, clientes, modelos)
            self._criar_contas_pagar(empresa)
            self._criar_caixa(empresa)

        self._resumo(empresa, pedidos)

    # ── Categorias ───────────────────────────────────────────────────────────
    def _criar_categorias(self, empresa):
        mapa = {}
        for slug, nome, ordem in CATEGORIAS:
            categoria, _ = Categoria.objects.update_or_create(
                empresa=empresa,
                slug=slug,
                defaults={"nome": nome, "ordem": ordem, "ativo": True},
            )
            mapa[slug] = categoria
        self.stdout.write(f"  • Categorias: {len(mapa)}")
        return mapa

    # ── Produtos e SKUs ──────────────────────────────────────────────────────
    def _criar_produtos(self, empresa, categorias):
        modelos = {}
        total_skus = 0
        for dados in PRODUTOS:
            modelo, _ = Modelo.objects.update_or_create(
                empresa=empresa,
                nome=dados["nome"],
                defaults={
                    "marca": dados["marca"],
                    "categoria": categorias[dados["categoria"]],
                    "lancamento": dados.get("lancamento", False),
                    "preco_varejo": Decimal(dados["preco_varejo"]),
                    "preco_atacado": Decimal(dados["preco_atacado"]),
                    "qtd_minima_atacado": dados["qtd_minima_atacado"],
                    "composicao": dados["composicao"],
                    "gramatura": dados["gramatura"],
                    "descricao": dados["descricao"],
                    "visivel_catalogo": True,
                },
            )
            modelos[dados["nome"]] = modelo
            total_skus += self._criar_grade(empresa, modelo, dados)

        self.stdout.write(
            f"  • Produtos/Modelos: {len(modelos)} | SKUs: {total_skus}"
        )
        return modelos

    def _criar_grade(self, empresa, modelo, dados):
        """Cria de 2 a 3 SKUs variando tamanho (P/M/G...) e cor real.

        Quando o produto tem apenas um tamanho (ex.: alguns brindes), varia a
        cor; quando tem apenas uma cor, varia o tamanho. Os pares (cor, tamanho)
        são sempre únicos, respeitando a constraint do modelo ``SKU``.
        """
        quantidade = max(2, min(3, dados.get("qtd_skus", 3)))
        cores = dados["cores"]
        tamanhos = dados["tamanhos"]
        usados = set()
        combos = []
        limite = len(cores) * len(tamanhos)
        indice = 0
        while len(combos) < quantidade and indice < limite:
            cor_nome, cor_hex = cores[indice % len(cores)]
            tamanho = tamanhos[indice % len(tamanhos)]
            indice += 1
            if (cor_nome, tamanho) in usados:
                continue
            usados.add((cor_nome, tamanho))
            combos.append((cor_nome, cor_hex, tamanho))

        for posicao, (cor_nome, cor_hex, tamanho) in enumerate(combos):
            estoque = max(dados["estoque_base"] - (posicao * 6), 5)
            SKU.objects.update_or_create(
                empresa=empresa,
                modelo=modelo,
                cor_nome=cor_nome,
                tamanho=tamanho,
                defaults={
                    "cor_hex": cor_hex,
                    "quantidade_estoque": estoque,
                    "codigo_barras": self._codigo_barras(modelo, cor_nome, tamanho),
                },
            )
        return len(combos)

    @staticmethod
    def _codigo_barras(modelo, cor_nome, tamanho):
        base = f"{modelo.pk}-{cor_nome}-{tamanho}"
        return hashlib.sha256(base.encode("utf-8")).hexdigest()[:12].upper()

    # ── Clientes ─────────────────────────────────────────────────────────────
    def _criar_clientes(self, empresa):
        clientes = []
        for dados in CLIENTES:
            if dados["tipo_pessoa"] == "PJ":
                documento = _gerar_cnpj(dados["doc_base"])
            else:
                documento = _gerar_cpf(dados["doc_base"])
            cliente, _ = Cliente.objects.update_or_create(
                email=dados["email"],
                defaults={
                    "empresa": empresa,
                    "nome_razao_social": dados["nome_razao_social"],
                    "tipo_pessoa": dados["tipo_pessoa"],
                    "cpf_cnpj": documento,
                    "whatsapp": dados["whatsapp"],
                    "cep": dados["cep"],
                    "endereco": dados["endereco"],
                    "numero": dados["numero"],
                    "bairro": dados["bairro"],
                    "cidade": dados["cidade"],
                    "estado": dados["estado"],
                    "is_active": True,
                },
            )
            if not cliente.has_usable_password():
                pass
            else:
                cliente.set_unusable_password()
                cliente.save(update_fields=["password"])
            clientes.append(cliente)

        self.stdout.write(f"  • Clientes (PF/PJ): {len(clientes)}")
        return clientes

    # ── Pedidos, Itens e Financeiro dos pedidos ──────────────────────────────
    def _criar_pedidos(self, empresa, clientes, modelos):
        hoje = timezone.localdate()
        pedidos = []
        for indice, plano in enumerate(PEDIDOS, start=1):
            cliente = clientes[plano["cliente"]]
            marcador = f"{TAG_DEMO}-{indice:02d}"

            pedido, _ = Pedido.objects.get_or_create(
                empresa=empresa,
                versao_termos=marcador,
                defaults={"cliente_nome": cliente.nome_razao_social},
            )
            pedido.cliente = cliente
            pedido.cliente_nome = cliente.nome_razao_social
            pedido.cliente_documento = cliente.cpf_cnpj
            pedido.cliente_whatsapp = cliente.whatsapp
            pedido.forma_pagamento = plano["forma"]
            pedido.tipo_entrega = plano["entrega"]
            pedido.endereco_entrega = (
                f"{cliente.endereco}, {cliente.numero} - {cliente.bairro}, "
                f"{cliente.cidade}/{cliente.estado}"
            )
            pedido.aceite_lgpd = True
            pedido.ip_aceite = "127.0.0.1"
            pedido.data_aceite = pedido.data_aceite or timezone.now()
            pedido.taxa_entrega = (
                Decimal("0.00")
                if plano["entrega"] == Pedido.TipoEntrega.RETIRADA_LOCAL
                else Decimal("25.00")
            )
            pedido.save()

            total_itens, valor_total = self._criar_itens(pedido, plano["itens"], modelos)
            pedido.total_itens = total_itens
            pedido.valor_total = valor_total
            pedido.save(update_fields=["total_itens", "valor_total"])

            self._criar_financeiro_pedido(empresa, pedido, plano, hoje)

            # Reafirma o status final após a sincronização disparada pelo financeiro.
            self._definir_status(pedido, plano["status"])
            pedidos.append(pedido)

        self.stdout.write(f"  • Pedidos: {len(pedidos)}")
        return pedidos

    def _criar_itens(self, pedido, itens, modelos):
        ItemPedido.objects.filter(pedido=pedido).delete()
        total_itens = 0
        valor_total = Decimal("0.00")
        for nome_modelo, quantidade in itens:
            modelo = modelos[nome_modelo]
            sku = modelo.skus.order_by("cor_nome", "tamanho").first()
            preco = modelo.preco_unitario_para(quantidade)
            ItemPedido.objects.create(
                pedido=pedido,
                sku=sku,
                quantidade=quantidade,
                preco_unitario=preco,
            )
            total_itens += quantidade
            valor_total += quantidade * preco
        return total_itens, valor_total

    def _criar_financeiro_pedido(self, empresa, pedido, plano, hoje):
        status = plano["status"]
        if status == "PENDENTE":
            return

        if status == "FATURADO":
            parcelas = plano.get("parcelas", 2)
            self._criar_parcelas_receber(empresa, pedido, parcelas, hoje)
        elif status == "ENTREGUE":
            self._criar_recebimento_pedido(empresa, pedido, plano, hoje)

    def _criar_parcelas_receber(self, empresa, pedido, quantidade, hoje):
        valor = pedido.valor_total or Decimal("0.00")
        base = (valor / quantidade).quantize(Decimal("0.01"))
        acumulado = Decimal("0.00")
        for numero in range(1, quantidade + 1):
            if numero == quantidade:
                valor_parcela = valor - acumulado
            else:
                valor_parcela = base
                acumulado += valor_parcela
            ContaReceber.objects.update_or_create(
                empresa=empresa,
                pedido=pedido,
                descricao=f"{TAG_DEMO} · Pedido #{pedido.pk} · parcela {numero}/{quantidade}",
                defaults={
                    "cliente": pedido.cliente,
                    "cliente_nome": pedido.cliente_nome,
                    "origem": ContaReceber.Origem.PEDIDO,
                    "forma_pagamento": ContaReceber.FormaPagamento.FATURADO_ATACADO,
                    "valor": valor_parcela,
                    "data_vencimento": hoje + timedelta(days=30 * numero),
                    "status": ContaReceber.Status.FATURADO_APROVADO,
                },
            )

    def _criar_recebimento_pedido(self, empresa, pedido, plano, hoje):
        conta, _ = ContaReceber.objects.update_or_create(
            empresa=empresa,
            pedido=pedido,
            descricao=f"{TAG_DEMO} · Recebimento do pedido #{pedido.pk}",
            defaults={
                "cliente": pedido.cliente,
                "cliente_nome": pedido.cliente_nome,
                "origem": ContaReceber.Origem.PEDIDO,
                "forma_pagamento": plano["forma"],
                "valor": pedido.valor_total,
                "data_vencimento": hoje - timedelta(days=2),
                "data_recebimento": hoje - timedelta(days=1),
                "status": ContaReceber.Status.PAGO,
            },
        )
        caixa = obter_caixa_do_dia(empresa, conta.data_recebimento)
        CaixaMovimentacao.objects.get_or_create(
            empresa=empresa,
            tipo=CaixaMovimentacao.Tipo.ENTRADA,
            conta_receber=conta,
            defaults={
                "caixa": caixa,
                "categoria": "Recebimento",
                "descricao": f"Recebimento do pedido #{pedido.pk} - {pedido.cliente_nome}",
                "valor": conta.valor,
                "forma_pagamento": plano["forma"],
                "pedido": pedido,
            },
        )

    @staticmethod
    def _definir_status(pedido, status):
        if status == "PENDENTE":
            pedido.status = Pedido.Status.AGUARDANDO_PAGAMENTO
            pedido.status_financeiro = Pedido.StatusFinanceiro.AGUARDANDO_PAGAMENTO
        elif status == "FATURADO":
            pedido.status = Pedido.Status.EM_PRODUCAO
            pedido.status_financeiro = Pedido.StatusFinanceiro.FATURADO_ATACADO
        elif status == "ENTREGUE":
            pedido.status = Pedido.Status.ENTREGUE
            pedido.status_financeiro = Pedido.StatusFinanceiro.PAGO_LIBERADO
        pedido.save(update_fields=["status", "status_financeiro"])

    # ── Contas a Pagar e saídas de Caixa ─────────────────────────────────────
    def _criar_contas_pagar(self, empresa):
        hoje = timezone.localdate()
        for fornecedor, categoria, descricao, valor, dias, pago in CONTAS_PAGAR:
            vencimento = hoje + timedelta(days=dias)
            conta, _ = ContaPagar.objects.update_or_create(
                empresa=empresa,
                descricao=descricao,
                defaults={
                    "fornecedor": fornecedor,
                    "categoria": categoria,
                    "valor": Decimal(valor),
                    "data_vencimento": vencimento,
                    "data_pagamento": hoje - timedelta(days=1) if pago else None,
                    "status": ContaPagar.Status.PAGO if pago else ContaPagar.Status.PENDENTE,
                },
            )
            if pago:
                caixa = obter_caixa_do_dia(empresa, conta.data_pagamento)
                CaixaMovimentacao.objects.get_or_create(
                    empresa=empresa,
                    tipo=CaixaMovimentacao.Tipo.SAIDA,
                    conta_pagar=conta,
                    defaults={
                        "caixa": caixa,
                        "categoria": "Pagamento",
                        "descricao": f"{fornecedor} - {descricao}",
                        "valor": conta.valor,
                    },
                )
        self.stdout.write(f"  • Contas a Pagar: {len(CONTAS_PAGAR)}")

    def _criar_caixa(self, empresa):
        hoje = timezone.localdate()
        caixa = obter_caixa_do_dia(empresa, hoje)
        if not caixa.saldo_inicial:
            caixa.saldo_inicial = Decimal("1500.00")
            caixa.save(update_fields=["saldo_inicial"])
        entradas = CaixaMovimentacao.objects.filter(
            empresa=empresa, tipo=CaixaMovimentacao.Tipo.ENTRADA
        ).count()
        saidas = CaixaMovimentacao.objects.filter(
            empresa=empresa, tipo=CaixaMovimentacao.Tipo.SAIDA
        ).count()
        self.stdout.write(f"  • Caixa: {entradas} entrada(s) e {saidas} saída(s)")

    # ── Limpeza ──────────────────────────────────────────────────────────────
    def _limpar(self, empresa):
        emails = [c["email"] for c in CLIENTES]
        nomes_modelos = [p["nome"] for p in PRODUTOS]
        slugs = [slug for slug, _, _ in CATEGORIAS]
        descricoes_pagar = [d for _, _, d, _, _, _ in CONTAS_PAGAR]

        with transaction.atomic():
            CaixaMovimentacao.objects.filter(empresa=empresa).filter(
                conta_receber__descricao__startswith=TAG_DEMO
            ).delete()
            CaixaMovimentacao.objects.filter(
                empresa=empresa, conta_pagar__descricao__in=descricoes_pagar
            ).delete()

            total_contas_receber = ContaReceber.objects.filter(
                empresa=empresa, pedido__versao_termos__startswith=TAG_DEMO
            ).count()
            ContaReceber.objects.filter(
                empresa=empresa, pedido__versao_termos__startswith=TAG_DEMO
            ).delete()

            total_contas_pagar = ContaPagar.objects.filter(
                empresa=empresa, descricao__in=descricoes_pagar
            ).count()
            ContaPagar.objects.filter(
                empresa=empresa, descricao__in=descricoes_pagar
            ).delete()

            pedidos = Pedido.objects.filter(
                empresa=empresa, versao_termos__startswith=TAG_DEMO
            )
            total_pedidos = pedidos.count()
            total_itens = ItemPedido.objects.filter(pedido__in=pedidos).count()
            pedidos.delete()

            modelos = Modelo.objects.filter(empresa=empresa, nome__in=nomes_modelos)
            total_skus = SKU.objects.filter(empresa=empresa, modelo__in=modelos).count()
            modelos.delete()

            total_categorias = Categoria.objects.filter(
                empresa=empresa, slug__in=slugs
            ).count()
            Categoria.objects.filter(empresa=empresa, slug__in=slugs).delete()

            total_clientes = Cliente.objects.filter(email__in=emails).count()
            Cliente.objects.filter(email__in=emails).delete()

        self.stdout.write(self.style.WARNING("Limpeza de demonstração concluída:"))
        self.stdout.write(
            f"  • Pedidos: {total_pedidos} (itens: {total_itens}) | "
            f"Contas a Receber: {total_contas_receber} | "
            f"Contas a Pagar: {total_contas_pagar}"
        )
        self.stdout.write(
            f"  • SKUs: {total_skus} | Categorias: {total_categorias} | "
            f"Clientes: {total_clientes}"
        )
        self.stdout.write(
            "  • Usuários, dados da empresa e migrações foram preservados."
        )

    # ── Resumo ───────────────────────────────────────────────────────────────
    def _resumo(self, empresa, pedidos):
        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "Demonstração de Estamparia/Serigrafia populada com sucesso:\n"
                f"  Empresa: {empresa.nome_fantasia} (/{empresa.slug}/)\n"
                f"  Catálogo: /catalogo/{empresa.slug}/\n"
                f"  Pedidos de demonstração: {len(pedidos)}"
            )
        )
