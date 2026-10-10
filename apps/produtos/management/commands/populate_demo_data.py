"""Popula a fábrica de demonstração com produtos de atacado e varejo.

Comando idempotente: pode ser executado várias vezes sem duplicar registros.
Cria a empresa (fábrica), 12 modelos reais com grade de cores/tamanhos e
preços de varejo e atacado.
"""

import hashlib
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.financeiro.models import CaixaDiario, ContaPagar, ContaReceber
from apps.produtos.models import Modelo, SKU
from apps.tenants.models import Empresa

TERMOS = (
    "Termos de Uso: pedidos sujeitos à confirmação de estoque e prazo de produção. "
    "Preços de atacado válidos a partir da quantidade mínima indicada por item. "
    "Produção iniciada mediante pagamento conforme combinado com o comercial."
)
PRIVACIDADE = (
    "Política de Privacidade: os dados informados são utilizados apenas para contato "
    "comercial e emissão do pedido, conforme a Lei Geral de Proteção de Dados (LGPD)."
)

FABRICA = {
    "nome_fantasia": "BC Modas Confecção",
    "cnpj": "12.345.678/0001-90",
    "slug": "bc-modas",
    "email": "comercial@bcmodas.com.br",
    "whatsapp_comercial": "(11) 99999-0000",
    "instagram": "@bcmodasoficial",
    "cor_primaria": "#7c3aed",
    "endereco_origem": "Rua das Confecções, 100 - Brás - São Paulo/SP",
}

CORES_NEUTRO = [("Preto", "#111111"), ("Branco", "#f8fafc"), ("Cinza Mescla", "#9ca3af")]
CORES_BASICO = [("Preto", "#111111"), ("Branco", "#f8fafc"), ("Azul Marinho", "#1e3a8a"), ("Vinho", "#7f1d1d")]
CORES_FIT = [("Preto", "#111111"), ("Cinza Chumbo", "#4b5563"), ("Rosa", "#ec4899"), ("Azul Petróleo", "#0f766e")]

TAMANHOS_ADULTO = ["PP", "P", "M", "G", "GG", "XG", "XGG"]

PRODUTOS = [
    {
        "nome": "Camiseta Oversized Premium",
        "marca": "BC Modas",
        "preco_varejo": "69.90",
        "preco_atacado": "44.90",
        "qtd_minima_atacado": 6,
        "composicao": "100% algodão penteado",
        "gramatura": "185g/m²",
        "descricao": "Camiseta oversized unissex com caimento amplo e gola reforçada.",
        "tabela_medidas_json": {
            "busto": "P:52 | M:54 | G:56 | GG:58 | XG:60 | XGG:62",
            "comprimento": "P:70 | M:72 | G:74 | GG:76 | XG:78 | XGG:80",
        },
        "cores": CORES_BASICO,
        "tamanhos": ["P", "M", "G", "GG", "XG", "XGG"],
        "estoque_base": 40,
    },
    {
        "nome": "Camiseta Básica Gola Careca",
        "marca": "BC Modas",
        "preco_varejo": "39.90",
        "preco_atacado": "24.90",
        "qtd_minima_atacado": 6,
        "composicao": "100% algodão fio 30.1",
        "gramatura": "160g/m²",
        "descricao": "Camiseta básica de gola careca, ideal para peça do dia a dia.",
        "tabela_medidas_json": {"busto": "P:48 | M:50 | G:52 | GG:54", "comprimento": "P:66 | M:68 | G:70 | GG:72"},
        "cores": CORES_NEUTRO,
        "tamanhos": ["P", "M", "G", "GG", "XG"],
        "estoque_base": 60,
    },
    {
        "nome": "Camiseta Manga Longa",
        "marca": "BC Modas",
        "preco_varejo": "59.90",
        "preco_atacado": "39.90",
        "qtd_minima_atacado": 6,
        "composicao": "100% algodão",
        "gramatura": "170g/m²",
        "descricao": "Camiseta manga longa com modelagem confortável.",
        "tabela_medidas_json": {},
        "cores": CORES_NEUTRO,
        "tamanhos": ["P", "M", "G", "GG"],
        "estoque_base": 35,
    },
    {
        "nome": "Moletom Canguru Flanelado",
        "marca": "BC Modas",
        "preco_varejo": "159.90",
        "preco_atacado": "109.90",
        "qtd_minima_atacado": 4,
        "composicao": "80% algodão, 20% poliéster",
        "gramatura": "330g/m²",
        "descricao": "Moletom com capuz, bolso canguru e interior flanelado.",
        "tabela_medidas_json": {"busto": "P:58 | M:60 | G:62 | GG:64"},
        "cores": CORES_BASICO,
        "tamanhos": ["P", "M", "G", "GG", "XG"],
        "estoque_base": 25,
    },
    {
        "nome": "Moletom Gola Careca",
        "marca": "BC Modas",
        "preco_varejo": "129.90",
        "preco_atacado": "89.90",
        "qtd_minima_atacado": 4,
        "composicao": "90% algodão, 10% poliéster",
        "gramatura": "300g/m²",
        "descricao": "Moletom gola careca sem capuz, punho e barra em ribana.",
        "tabela_medidas_json": {},
        "cores": CORES_NEUTRO,
        "tamanhos": ["P", "M", "G", "GG"],
        "estoque_base": 30,
    },
    {
        "nome": "Jaqueta Corta-Vento",
        "marca": "BC Modas",
        "preco_varejo": "149.90",
        "preco_atacado": "99.90",
        "qtd_minima_atacado": 4,
        "composicao": "Poliamida com forro em tafetá",
        "gramatura": "Média",
        "descricao": "Jaqueta corta-vento com capuz, zíper e bolsos laterais.",
        "tabela_medidas_json": {},
        "cores": [("Preto", "#111111"), ("Azul Royal", "#1d4ed8"), ("Verde Militar", "#3f6212")],
        "tamanhos": ["P", "M", "G", "GG", "XG"],
        "estoque_base": 18,
    },
    {
        "nome": "Calça Jogger Moletom",
        "marca": "BC Modas",
        "preco_varejo": "119.90",
        "preco_atacado": "79.90",
        "qtd_minima_atacado": 4,
        "composicao": "80% algodão, 20% poliéster",
        "gramatura": "300g/m²",
        "descricao": "Calça jogger com punho, cordão ajustável e bolsos.",
        "tabela_medidas_json": {"cintura": "P:38 | M:40 | G:42 | GG:44", "comprimento": "P:98 | M:100 | G:102 | GG:104"},
        "cores": CORES_NEUTRO,
        "tamanhos": ["P", "M", "G", "GG"],
        "estoque_base": 26,
    },
    {
        "nome": "Calça Jeans Skinny",
        "marca": "BC Modas",
        "preco_varejo": "139.90",
        "preco_atacado": "94.90",
        "qtd_minima_atacado": 4,
        "composicao": "98% algodão, 2% elastano",
        "gramatura": "12oz",
        "descricao": "Calça jeans skinny com lavagem escura e cintura alta.",
        "tabela_medidas_json": {"cintura": "P:38 | M:40 | G:42 | GG:44", "comprimento": "P:100 | M:102 | G:104 | GG:106"},
        "cores": [("Azul Escuro", "#1e3a8a"), ("Preto", "#111111")],
        "tamanhos": ["P", "M", "G", "GG"],
        "estoque_base": 22,
    },
    {
        "nome": "Shorts Moletom",
        "marca": "BC Modas",
        "preco_varejo": "79.90",
        "preco_atacado": "49.90",
        "qtd_minima_atacado": 6,
        "composicao": "80% algodão, 20% poliéster",
        "gramatura": "280g/m²",
        "descricao": "Shorts de moletom com cordão e bolsos laterais.",
        "tabela_medidas_json": {},
        "cores": CORES_NEUTRO,
        "tamanhos": ["P", "M", "G", "GG"],
        "estoque_base": 45,
    },
    {
        "nome": "Top Fitness Dry Fit",
        "marca": "BC Fit",
        "preco_varejo": "69.90",
        "preco_atacado": "44.90",
        "qtd_minima_atacado": 6,
        "composicao": "Poliamida com elastano",
        "gramatura": "Dry fit",
        "descricao": "Top fitness com sustentação média e tecido de secagem rápida.",
        "tabela_medidas_json": {},
        "cores": CORES_FIT,
        "tamanhos": ["P", "M", "G", "GG"],
        "estoque_base": 38,
    },
    {
        "nome": "Legging Fitness Alta Compressão",
        "marca": "BC Fit",
        "preco_varejo": "99.90",
        "preco_atacado": "64.90",
        "qtd_minima_atacado": 6,
        "composicao": "Poliamida com elastano",
        "gramatura": "Alta compressão",
        "descricao": "Legging de alta compressão com cós largo e bolso lateral.",
        "tabela_medidas_json": {},
        "cores": CORES_FIT,
        "tamanhos": ["P", "M", "G", "GG"],
        "estoque_base": 34,
    },
    {
        "nome": "Regata Dry Fit Masculina",
        "marca": "BC Fit",
        "preco_varejo": "54.90",
        "preco_atacado": "34.90",
        "qtd_minima_atacado": 6,
        "composicao": "Poliéster com elastano",
        "gramatura": "Dry fit",
        "descricao": "Regata masculina com tecido respirável para treino.",
        "tabela_medidas_json": {},
        "cores": [("Preto", "#111111"), ("Cinza Chumbo", "#4b5563"), ("Azul Marinho", "#1e3a8a")],
        "tamanhos": ["P", "M", "G", "GG", "XG"],
        "estoque_base": 42,
    },
]


class Command(BaseCommand):
    help = (
        "Popula dados de demonstração da fábrica (empresa, modelos, grade de SKUs "
        "com preços de varejo e atacado). Idempotente."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Remove os produtos da fábrica demo antes de recriar.",
        )

    def handle(self, *args, **options):
        with transaction.atomic():
            empresa = self._criar_empresa()
            if options["reset"]:
                self.stdout.write(self.style.WARNING("Removendo modelos anteriores..."))
                Modelo.objects.filter(empresa=empresa).delete()
            self._criar_produtos(empresa)
            self._criar_financeiro(empresa)

        self._resumo(empresa)

    def _criar_empresa(self):
        empresa, criada = Empresa.objects.update_or_create(
            cnpj=FABRICA["cnpj"],
            defaults={
                "nome_fantasia": FABRICA["nome_fantasia"],
                "slug": FABRICA["slug"],
                "email": FABRICA["email"],
                "whatsapp_comercial": FABRICA["whatsapp_comercial"],
                "instagram": FABRICA["instagram"],
                "cor_primaria": FABRICA["cor_primaria"],
                "endereco_origem": FABRICA["endereco_origem"],
                "status": Empresa.Status.ATIVO,
                "termos_uso": TERMOS,
                "politica_privacidade": PRIVACIDADE,
            },
        )
        acao = "criada" if criada else "atualizada"
        self.stdout.write(f"  • Fábrica {acao}: {empresa.nome_fantasia} (/{empresa.slug}/)")
        return empresa

    def _criar_produtos(self, empresa):
        for dados in PRODUTOS:
            modelo, _ = Modelo.objects.update_or_create(
                empresa=empresa,
                nome=dados["nome"],
                defaults={
                    "marca": dados["marca"],
                    "preco_varejo": Decimal(dados["preco_varejo"]),
                    "preco_atacado": Decimal(dados["preco_atacado"]),
                    "qtd_minima_atacado": dados["qtd_minima_atacado"],
                    "composicao": dados["composicao"],
                    "gramatura": dados["gramatura"],
                    "descricao": dados["descricao"],
                    "tabela_medidas_json": dados["tabela_medidas_json"],
                    "visivel_catalogo": True,
                },
            )
            for indice_cor, (cor_nome, cor_hex) in enumerate(dados["cores"]):
                for indice_tam, tamanho in enumerate(dados["tamanhos"]):
                    estoque = dados["estoque_base"] - (indice_tam * 3) - (indice_cor * 2)
                    SKU.objects.update_or_create(
                        empresa=empresa,
                        modelo=modelo,
                        cor_nome=cor_nome,
                        tamanho=tamanho,
                        defaults={
                            "cor_hex": cor_hex,
                            "quantidade_estoque": max(estoque, 0),
                            "codigo_barras": self._codigo_barras(modelo, cor_nome, tamanho),
                        },
                    )
            self.stdout.write(f"    · {modelo.nome} ({modelo.qtd_minima_atacado}+ p/ atacado)")

    @staticmethod
    def _codigo_barras(modelo, cor_nome, tamanho):
        base = f"{modelo.pk}-{cor_nome}-{tamanho}"
        return hashlib.sha256(base.encode("utf-8")).hexdigest()[:12].upper()

    def _criar_financeiro(self, empresa):
        hoje = timezone.localdate()
        contas_pagar = [
            ("Malharia São Paulo", "MATERIA_PRIMA", "Compra de malha algodão", "3500.00", hoje + timedelta(days=5)),
            ("Folha de Pagamento", "FOLHA_PAGAMENTO", "Folha da equipe de produção", "8200.00", hoje + timedelta(days=2)),
            ("Enel Distribuição", "OPERACIONAL", "Energia elétrica da fábrica", "950.00", hoje - timedelta(days=1)),
            ("Receita Federal", "IMPOSTOS", "DAS Simples Nacional", "1200.00", hoje + timedelta(days=10)),
        ]
        for fornecedor, categoria, descricao, valor, vencimento in contas_pagar:
            ContaPagar.objects.update_or_create(
                empresa=empresa,
                descricao=descricao,
                defaults={
                    "fornecedor": fornecedor,
                    "categoria": categoria,
                    "valor": Decimal(valor),
                    "data_vencimento": vencimento,
                    "status": ContaPagar.Status.PENDENTE,
                },
            )

        contas_receber = [
            {
                "descricao": "Venda atacado - Lojista Centro",
                "cliente_nome": "Lojista Centro",
                "valor": Decimal("2100.00"),
                "vencimento": hoje + timedelta(days=3),
                "forma": ContaReceber.FormaPagamento.FATURADO_ATACADO,
                "status": ContaReceber.Status.PENDENTE,
            },
            {
                "descricao": "Venda balcão - Boutique Estação",
                "cliente_nome": "Boutique Estação",
                "valor": Decimal("780.00"),
                "vencimento": hoje - timedelta(days=2),
                "forma": ContaReceber.FormaPagamento.PIX,
                "status": ContaReceber.Status.PAGO,
            },
        ]
        for dados in contas_receber:
            ContaReceber.objects.update_or_create(
                empresa=empresa,
                descricao=dados["descricao"],
                defaults={
                    "origem": ContaReceber.Origem.EXTERNA,
                    "cliente_nome": dados["cliente_nome"],
                    "valor": dados["valor"],
                    "data_vencimento": dados["vencimento"],
                    "data_recebimento": hoje if dados["status"] == ContaReceber.Status.PAGO else None,
                    "forma_pagamento": dados["forma"],
                    "status": dados["status"],
                },
            )

        CaixaDiario.objects.update_or_create(
            empresa=empresa,
            data=hoje,
            defaults={"saldo_inicial": Decimal("500.00")},
        )
        self.stdout.write(
            f"    · Financeiro: {len(contas_pagar)} conta(s) a pagar e "
            f"{len(contas_receber)} conta(s) a receber"
        )

    def _resumo(self, empresa):
        modelos = Modelo.objects.filter(empresa=empresa)
        skus = SKU.objects.filter(empresa=empresa)
        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "População de demonstração concluída:\n"
                f"  Fábrica: {empresa.nome_fantasia} (/{empresa.slug}/)\n"
                f"  Modelos: {modelos.count()} | SKUs: {skus.count()}"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"  Catálogo: /catalogo/{empresa.slug}/"
            )
        )
