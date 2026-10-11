"""Popula o e-commerce de demonstração do BC Modas com dados fictícios.

Comando idempotente (usa ``get_or_create``): pode ser executado várias vezes
sem duplicar registros. Cria 4 categorias, 12 produtos com grade de tamanhos
P/M/G/GG, cores, fotos (URLs de placeholder) e 6 clientes de teste com
CPF/WhatsApp/endereço fictícios.

Uso:
    python manage.py popular_demo          # cria/atualiza os dados de demo
    python manage.py popular_demo --clean  # remove apenas os dados de demo

O ``--clean`` remove somente o que este comando criou (produtos, categorias e
clientes listados abaixo), preservando superusuários, configurações da empresa
(tenant) e migrações do sistema.
"""

import hashlib
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from apps.clientes.models import Cliente
from apps.produtos.models import Categoria, Modelo, SKU
from apps.tenants.models import Empresa

TAMANHOS = ["P", "M", "G", "GG"]

CORES_FEMININO = [
    ("Preto", "#111111"),
    ("Off White", "#f5f5f4"),
    ("Lilás", "#c084fc"),
    ("Vermelho", "#dc2626"),
]
CORES_MASCULINO = [
    ("Preto", "#111111"),
    ("Azul Marinho", "#1e3a8a"),
    ("Cinza Mescla", "#9ca3af"),
    ("Verde Militar", "#3f6212"),
]
CORES_ACESSORIOS = [
    ("Preto", "#111111"),
    ("Marrom Caramelo", "#a16207"),
    ("Bege", "#d6c7a1"),
]
CORES_CALCADOS = [
    ("Branco", "#f8fafc"),
    ("Preto", "#111111"),
    ("Caramelo", "#b45309"),
]

CATEGORIAS = [
    ("Feminino", 0),
    ("Masculino", 1),
    ("Acessórios", 2),
    ("Calçados", 3),
]

PRODUTOS = [
    {
        "nome": "Vestido Midi Floral",
        "marca": "BC Modas",
        "categoria": "Feminino",
        "lancamento": True,
        "preco_varejo": "189.90",
        "preco_atacado": "129.90",
        "qtd_minima_atacado": 4,
        "composicao": "100% viscose",
        "gramatura": "Leve",
        "descricao": "Vestido midi com estampa floral exclusiva, alças finas e caimento fluido.",
        "cores": CORES_FEMININO,
        "estoque_base": 30,
        "fotos": ["vestido-midi-floral-1", "vestido-midi-floral-2"],
    },
    {
        "nome": "Blusa Cropped Canelada",
        "marca": "BC Modas",
        "categoria": "Feminino",
        "preco_varejo": "89.90",
        "preco_atacado": "59.90",
        "qtd_minima_atacado": 6,
        "composicao": "92% poliéster, 8% elastano",
        "gramatura": "Canelada",
        "descricao": "Blusa cropped de tecido canelado com manga longa e toque macio.",
        "cores": CORES_FEMININO,
        "estoque_base": 40,
        "fotos": ["blusa-cropped-canelada-1", "blusa-cropped-canelada-2"],
    },
    {
        "nome": "Calça Wide Leg Alfaiataria",
        "marca": "BC Modas",
        "categoria": "Feminino",
        "preco_varejo": "179.90",
        "preco_atacado": "119.90",
        "qtd_minima_atacado": 4,
        "composicao": "88% poliéster, 12% viscose",
        "gramatura": "Média",
        "descricao": "Calça wide leg de alfaiataria com cintura alta, bolsos e barra ampla.",
        "cores": CORES_FEMININO,
        "estoque_base": 24,
        "fotos": ["calca-wide-leg-1", "calca-wide-leg-2"],
    },
    {
        "nome": "Camisa Linho Manga Longa",
        "marca": "BC Modas",
        "categoria": "Masculino",
        "lancamento": True,
        "preco_varejo": "169.90",
        "preco_atacado": "114.90",
        "qtd_minima_atacado": 4,
        "composicao": "55% linho, 45% viscose",
        "gramatura": "Leve",
        "descricao": "Camisa de linho com modelagem relaxada, colarinho italiano e costura reforçada.",
        "cores": CORES_MASCULINO,
        "estoque_base": 28,
        "fotos": ["camisa-linho-manga-longa-1", "camisa-linho-manga-longa-2"],
    },
    {
        "nome": "Camiseta Heavy Cotton",
        "marca": "BC Modas",
        "categoria": "Masculino",
        "preco_varejo": "99.90",
        "preco_atacado": "64.90",
        "qtd_minima_atacado": 6,
        "composicao": "100% algodão penteado",
        "gramatura": "220g/m²",
        "descricao": "Camiseta heavy cotton com gola dupla e caimento oversized estruturado.",
        "cores": CORES_MASCULINO,
        "estoque_base": 55,
        "fotos": ["camiseta-heavy-cotton-1", "camiseta-heavy-cotton-2"],
    },
    {
        "nome": "Polo Piquet Premium",
        "marca": "BC Modas",
        "categoria": "Masculino",
        "preco_varejo": "139.90",
        "preco_atacado": "94.90",
        "qtd_minima_atacado": 4,
        "composicao": "100% algodão piquet",
        "gramatura": "Piquet",
        "descricao": "Camisa polo em piquet premium com gola ribana e botões nacarados.",
        "cores": CORES_MASCULINO,
        "estoque_base": 36,
        "fotos": ["polo-piquet-premium-1", "polo-piquet-premium-2"],
    },
    {
        "nome": "Bolsa Tote Couro Eco",
        "marca": "BC Acessórios",
        "categoria": "Acessórios",
        "lancamento": True,
        "preco_varejo": "219.90",
        "preco_atacado": "149.90",
        "qtd_minima_atacado": 3,
        "composicao": "Couro ecológico",
        "gramatura": "Alta",
        "descricao": "Bolsa tote espaçosa em couro ecológico com alças reforçadas e bolso interno.",
        "cores": CORES_ACESSORIOS,
        "estoque_base": 20,
        "fotos": ["bolsa-tote-couro-eco-1", "bolsa-tote-couro-eco-2"],
    },
    {
        "nome": "Cinto de Couro Fivela Quadrada",
        "marca": "BC Acessórios",
        "categoria": "Acessórios",
        "preco_varejo": "89.90",
        "preco_atacado": "54.90",
        "qtd_minima_atacado": 6,
        "composicao": "Couro legítimo",
        "gramatura": "Média",
        "descricao": "Cinto de couro legítimo com fivela metálica quadrada e acabamento fosco.",
        "cores": CORES_ACESSORIOS,
        "estoque_base": 45,
        "fotos": ["cinto-couro-fivela-1"],
    },
    {
        "nome": "Óculos de Sol Retrô",
        "marca": "BC Acessórios",
        "categoria": "Acessórios",
        "preco_varejo": "129.90",
        "preco_atacado": "84.90",
        "qtd_minima_atacado": 6,
        "composicao": "Acetato com lentes UV400",
        "gramatura": "Leve",
        "descricao": "Óculos de sol estilo retrô com proteção UV400 e hastes flexíveis.",
        "cores": CORES_ACESSORIOS,
        "estoque_base": 50,
        "fotos": ["oculos-sol-retro-1", "oculos-sol-retro-2"],
    },
    {
        "nome": "Tênis Casual Branco",
        "marca": "BC Calçados",
        "categoria": "Calçados",
        "preco_varejo": "259.90",
        "preco_atacado": "179.90",
        "qtd_minima_atacado": 3,
        "composicao": "Couro sintético e solado de borracha",
        "gramatura": "Alta",
        "descricao": "Tênis casual branco minimalista com solado de borracha antiderrapante.",
        "cores": CORES_CALCADOS,
        "estoque_base": 22,
        "fotos": ["tenis-casual-branco-1", "tenis-casual-branco-2"],
    },
    {
        "nome": "Sandália Salto Bloco",
        "marca": "BC Calçados",
        "categoria": "Calçados",
        "lancamento": True,
        "preco_varejo": "179.90",
        "preco_atacado": "119.90",
        "qtd_minima_atacado": 3,
        "composicao": "Napa sintética",
        "gramatura": "Média",
        "descricao": "Sandália com salto bloco confortável, tiras finas e fechamento por fivela.",
        "cores": CORES_CALCADOS,
        "estoque_base": 18,
        "fotos": ["sandalia-salto-bloco-1", "sandalia-salto-bloco-2"],
    },
    {
        "nome": "Sapatênis Couro",
        "marca": "BC Calçados",
        "categoria": "Calçados",
        "preco_varejo": "239.90",
        "preco_atacado": "159.90",
        "qtd_minima_atacado": 3,
        "composicao": "Couro legítimo",
        "gramatura": "Alta",
        "descricao": "Sapatênis em couro legítimo com palmilha acolchoada e visual versátil.",
        "cores": CORES_CALCADOS,
        "estoque_base": 16,
        "fotos": ["sapatenis-couro-1", "sapatenis-couro-2"],
    },
]

CLIENTES = [
    {
        "nome_razao_social": "Ana Beatriz Souza",
        "email": "ana.souza@cliente-demo.bcmodas.com",
        "whatsapp": "(11) 98888-1001",
        "cpf_base": "123456789",
        "cep": "01310-100",
        "endereco": "Avenida Paulista",
        "numero": "1000",
        "bairro": "Bela Vista",
        "cidade": "São Paulo",
        "estado": "SP",
    },
    {
        "nome_razao_social": "Carlos Eduardo Lima",
        "email": "carlos.lima@cliente-demo.bcmodas.com",
        "whatsapp": "(21) 99876-2002",
        "cpf_base": "987654321",
        "cep": "22041-011",
        "endereco": "Rua Barata Ribeiro",
        "numero": "502",
        "bairro": "Copacabana",
        "cidade": "Rio de Janeiro",
        "estado": "RJ",
    },
    {
        "nome_razao_social": "Fernanda Oliveira",
        "email": "fernanda.oliveira@cliente-demo.bcmodas.com",
        "whatsapp": "(31) 98765-3003",
        "cpf_base": "111444777",
        "cep": "30130-009",
        "endereco": "Rua da Bahia",
        "numero": "1200",
        "bairro": "Centro",
        "cidade": "Belo Horizonte",
        "estado": "MG",
    },
    {
        "nome_razao_social": "João Pedro Martins",
        "email": "joao.martins@cliente-demo.bcmodas.com",
        "whatsapp": "(41) 99123-4004",
        "cpf_base": "222555888",
        "cep": "80420-090",
        "endereco": "Rua Comendador Araújo",
        "numero": "431",
        "bairro": "Batel",
        "cidade": "Curitiba",
        "estado": "PR",
    },
    {
        "nome_razao_social": "Mariana Costa",
        "email": "mariana.costa@cliente-demo.bcmodas.com",
        "whatsapp": "(51) 98234-5005",
        "cpf_base": "333666999",
        "cep": "90050-170",
        "endereco": "Rua dos Andradas",
        "numero": "1001",
        "bairro": "Centro Histórico",
        "cidade": "Porto Alegre",
        "estado": "RS",
    },
    {
        "nome_razao_social": "Rafael Almeida",
        "email": "rafael.almeida@cliente-demo.bcmodas.com",
        "whatsapp": "(71) 99555-6006",
        "cpf_base": "456789123",
        "cep": "40170-110",
        "endereco": "Avenida Oceânica",
        "numero": "250",
        "bairro": "Barra",
        "cidade": "Salvador",
        "estado": "BA",
    },
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


def _fotos_urls(sementes):
    """Monta URLs válidas de imagens de placeholder para o catálogo."""
    return [
        f"https://picsum.photos/seed/bcmodas-{semente}/800/1000"
        for semente in sementes
    ]


class Command(BaseCommand):
    help = (
        "Popula o e-commerce de demonstração com categorias, produtos e clientes "
        "fictícios. Idempotente. Use --clean para remover apenas os dados de demo."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--clean",
            action="store_true",
            help=(
                "Remove apenas os dados de demonstração criados por este comando, "
                "preservando superusuários, dados da empresa e migrações."
            ),
        )

    def handle(self, *args, **options):
        empresa = Empresa.obter_fabrica()
        if empresa is None:
            raise CommandError(
                "Nenhuma empresa (fábrica) cadastrada. "
                "Cadastre a empresa no admin antes de popular a demonstração."
            )

        if options["clean"]:
            self._limpar(empresa)
            return

        with transaction.atomic():
            categorias = self._criar_categorias(empresa)
            self._criar_produtos(empresa, categorias)
            self._criar_clientes(empresa)

        self._resumo(empresa)

    # ── Criação ──────────────────────────────────────────────────────────────
    def _criar_categorias(self, empresa):
        mapa = {}
        for nome, ordem in CATEGORIAS:
            categoria, criada = Categoria.objects.get_or_create(
                empresa=empresa,
                slug=slugify(nome)[:90],
                defaults={"nome": nome, "ordem": ordem, "ativo": True},
            )
            mapa[nome] = categoria
        self.stdout.write(f"  • Categorias de demonstração: {len(mapa)}")
        return mapa

    def _criar_produtos(self, empresa, categorias):
        modelos, skus = 0, 0
        for dados in PRODUTOS:
            categoria = categorias[dados["categoria"]]
            defaults = {
                "marca": dados["marca"],
                "categoria": categoria,
                "lancamento": dados.get("lancamento", False),
                "preco_varejo": Decimal(dados["preco_varejo"]),
                "preco_atacado": Decimal(dados["preco_atacado"]),
                "qtd_minima_atacado": dados["qtd_minima_atacado"],
                "composicao": dados["composicao"],
                "gramatura": dados["gramatura"],
                "descricao": dados["descricao"],
                "visivel_catalogo": True,
            }
            for indice, url in enumerate(_fotos_urls(dados["fotos"]), start=1):
                defaults[f"foto_{indice}"] = url

            modelo, _ = Modelo.objects.get_or_create(
                empresa=empresa, nome=dados["nome"], defaults=defaults
            )
            modelos += 1

            for indice_cor, (cor_nome, cor_hex) in enumerate(dados["cores"]):
                for indice_tam, tamanho in enumerate(TAMANHOS):
                    estoque = max(
                        dados["estoque_base"] - (indice_tam * 3) - (indice_cor * 2), 0
                    )
                    _, criado = SKU.objects.get_or_create(
                        empresa=empresa,
                        modelo=modelo,
                        cor_nome=cor_nome,
                        tamanho=tamanho,
                        defaults={
                            "cor_hex": cor_hex,
                            "quantidade_estoque": estoque,
                            "codigo_barras": self._codigo_barras(
                                modelo, cor_nome, tamanho
                            ),
                        },
                    )
                    skus += 1 if criado else 0

        self.stdout.write(
            f"  • Produtos de demonstração: {modelos} (SKUs novos: {skus})"
        )

    def _criar_clientes(self, empresa):
        criados = 0
        for dados in CLIENTES:
            cliente, criado = Cliente.objects.get_or_create(
                email=dados["email"],
                defaults={
                    "empresa": empresa,
                    "nome_razao_social": dados["nome_razao_social"],
                    "tipo_pessoa": Cliente.TipoPessoa.PF,
                    "cpf_cnpj": _gerar_cpf(dados["cpf_base"]),
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
            if criado:
                cliente.set_unusable_password()
                cliente.save(update_fields=["password"])
                criados += 1

        self.stdout.write(
            f"  • Clientes de demonstração: {len(CLIENTES)} (novos: {criados})"
        )

    @staticmethod
    def _codigo_barras(modelo, cor_nome, tamanho):
        base = f"{modelo.pk}-{cor_nome}-{tamanho}"
        return hashlib.sha256(base.encode("utf-8")).hexdigest()[:12].upper()

    # ── Limpeza ──────────────────────────────────────────────────────────────
    def _limpar(self, empresa):
        nomes_modelos = [p["nome"] for p in PRODUTOS]
        slugs_categorias = [slugify(nome)[:90] for nome, _ in CATEGORIAS]
        emails = [c["email"] for c in CLIENTES]

        with transaction.atomic():
            modelos = Modelo.objects.filter(empresa=empresa, nome__in=nomes_modelos)
            total_modelos = modelos.count()
            total_skus = SKU.objects.filter(
                empresa=empresa, modelo__in=modelos
            ).count()
            modelos.delete()

            total_categorias = Categoria.objects.filter(
                empresa=empresa, slug__in=slugs_categorias
            ).count()
            Categoria.objects.filter(
                empresa=empresa, slug__in=slugs_categorias
            ).delete()

            total_clientes = Cliente.objects.filter(email__in=emails).count()
            Cliente.objects.filter(email__in=emails).delete()

        self.stdout.write(self.style.WARNING("Limpeza de demonstração concluída:"))
        self.stdout.write(
            f"  • Produtos removidos: {total_modelos} "
            f"(SKUs: {total_skus}) | Categorias: {total_categorias} | "
            f"Clientes: {total_clientes}"
        )
        self.stdout.write(
            "  • Superusuários, dados da empresa e migrações foram preservados."
        )

    def _resumo(self, empresa):
        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "Demonstração populada com sucesso:\n"
                f"  Empresa: {empresa.nome_fantasia} (/{empresa.slug}/)\n"
                f"  Catálogo: /catalogo/{empresa.slug}/"
            )
        )
