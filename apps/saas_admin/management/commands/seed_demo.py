import hashlib
from datetime import timedelta
from decimal import Decimal

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.pedidos.models import ItemPedido, Pedido
from apps.produtos.models import Modelo, SKU
from apps.tenants.models import Empresa, Plano
from apps.usuarios.models import Usuario

PASSWORD_PADRAO = "Demo123!"

TERMOS = (
    "Termos de Uso: pedidos sujeitos à confirmação de estoque e prazo. "
    "Produção mediante pagamento conforme combinado com o comercial."
)
PRIVACIDADE = (
    "Política de Privacidade: os dados informados são utilizados apenas para "
    "contato comercial e emissão do pedido, conforme a LGPD."
)

EMPRESAS = [
    {
        "nome_fantasia": "BC Modas Demo",
        "cnpj": "12.345.678/0001-90",
        "slug": "bc-modas-demo",
        "email": "contato@bcmodasdemo.com.br",
        "whatsapp_comercial": "(11) 99999-0000",
        "instagram": "@bcmodasdemo",
        "cor_primaria": "#7c3aed",
        "plano": "Pro",
        "endereco_origem": "Rua das Confecções, 100 - São Paulo/SP",
        "modelos": [
            {
                "nome": "Camiseta Oversized",
                "marca": "BC Modas",
                "preco_varejo": "59.90",
                "composicao": "100% algodão",
                "gramatura": "180g",
                "descricao": "Camiseta oversized unissex com caimento amplo.",
                "tabela_medidas_json": {
                    "busto": "P:52 | M:54 | G:56 | GG:58",
                    "comprimento": "P:70 | M:72 | G:74 | GG:76",
                },
                "cores": [("Preto", "#111111"), ("Branco", "#f8fafc"), ("Vinho", "#7f1d1d")],
                "tamanhos": ["P", "M", "G", "GG"],
                "estoque_base": 25,
            },
            {
                "nome": "Moletom Canguru",
                "marca": "BC Modas",
                "preco_varejo": "139.90",
                "composicao": "80% algodão, 20% poliéster",
                "gramatura": "320g",
                "descricao": "Moletom com capuz e bolso canguru.",
                "tabela_medidas_json": {"busto": "P:56 | M:58 | G:60", "comprimento": "P:68 | M:70 | G:72"},
                "cores": [("Cinza Mescla", "#9ca3af"), ("Preto", "#111111")],
                "tamanhos": ["P", "M", "G"],
                "estoque_base": 18,
            },
            {
                "nome": "Legging Fitness",
                "marca": "BC Modas",
                "preco_varejo": "89.90",
                "composicao": "Poliamida com elastano",
                "gramatura": "Médio",
                "descricao": "Legging de alta compressão para treino.",
                "tabela_medidas_json": {},
                "cores": [("Preto", "#111111"), ("Azul Marinho", "#1e3a8a")],
                "tamanhos": ["P", "M", "G", "GG"],
                "estoque_base": 30,
            },
        ],
        "equipe": [
            ("gerente.demo", "GERENTE", "Gerente", "BC Modas"),
            ("vendas.demo", "VENDAS", "Vendedor", "BC Modas"),
            ("financeiro.demo", "FINANCEIRO", "Financeiro", "BC Modas"),
        ],
    },
    {
        "nome_fantasia": "Moda Praia Carioca",
        "cnpj": "23.456.789/0001-01",
        "slug": "moda-praia-carioca",
        "email": "vendas@modapraiacarioca.com.br",
        "whatsapp_comercial": "(21) 98888-1111",
        "instagram": "@modapraiacarioca",
        "cor_primaria": "#0ea5e9",
        "plano": "Enterprise",
        "endereco_origem": "Av. Atlântica, 500 - Rio de Janeiro/RJ",
        "modelos": [
            {
                "nome": "Biquíni Cortininha",
                "marca": "Carioca",
                "preco_varejo": "74.90",
                "composicao": "Poliamida e elastano",
                "gramatura": "Médio",
                "descricao": "Biquíni cortininha com forro.",
                "tabela_medidas_json": {},
                "cores": [("Vermelho", "#dc2626"), ("Verde Água", "#2dd4bf"), ("Preto", "#111111")],
                "tamanhos": ["P", "M", "G"],
                "estoque_base": 20,
            },
            {
                "nome": "Maiô Nadador",
                "marca": "Carioca",
                "preco_varejo": "129.90",
                "composicao": "Poliamida com proteção UV",
                "gramatura": "Médio",
                "descricao": "Maiô nadador com alças ajustáveis.",
                "tabela_medidas_json": {},
                "cores": [("Preto", "#111111"), ("Azul Royal", "#1d4ed8")],
                "tamanhos": ["P", "M", "G", "GG"],
                "estoque_base": 15,
            },
        ],
        "equipe": [
            ("gerente.praia", "GERENTE", "Gerente", "Praia"),
            ("compras.praia", "COMPRAS", "Compras", "Praia"),
        ],
    },
    {
        "nome_fantasia": "Jeans & Cia Confecções",
        "cnpj": "34.567.890/0001-12",
        "slug": "jeans-e-cia",
        "email": "contato@jeansecia.com.br",
        "whatsapp_comercial": "(31) 97777-2222",
        "instagram": "@jeansecia",
        "cor_primaria": "#0f766e",
        "plano": "Starter",
        "endereco_origem": "Rua do Comércio, 45 - Belo Horizonte/MG",
        "modelos": [
            {
                "nome": "Calça Jeans Skinny",
                "marca": "Jeans & Cia",
                "preco_varejo": "119.90",
                "composicao": "98% algodão, 2% elastano",
                "gramatura": "12oz",
                "descricao": "Calça jeans skinny com lavagem escura.",
                "tabela_medidas_json": {"cintura": "P:38 | M:40 | G:42 | GG:44", "comprimento": "P:100 | M:102 | G:104"},
                "cores": [("Azul Escuro", "#1e3a8a"), ("Preto", "#111111")],
                "tamanhos": ["P", "M", "G", "GG"],
                "estoque_base": 22,
            },
            {
                "nome": "Jaqueta Jeans Oversized",
                "marca": "Jeans & Cia",
                "preco_varejo": "189.90",
                "composicao": "100% algodão",
                "gramatura": "14oz",
                "descricao": "Jaqueta jeans oversized com botões metálicos.",
                "tabela_medidas_json": {},
                "cores": [("Azul Claro", "#60a5fa")],
                "tamanhos": ["M", "G", "GG"],
                "estoque_base": 12,
            },
        ],
        "equipe": [
            ("gerente.jeans", "GERENTE", "Gerente", "Jeans"),
            ("vendas.jeans", "VENDAS", "Vendedor", "Jeans"),
        ],
    },
]

CLIENTES = [
    ("Lojista Centro Modas", "11.222.333/0001-44", "(11) 97777-3333"),
    ("Boutique Estação", "", "(21) 96666-4444"),
    ("Loja da Praça", "44.555.666/0001-77", "(31) 95555-5555"),
    ("Multimarcas Sol", "", "(41) 94444-6666"),
]

STATUS_PEDIDOS = [
    Pedido.Status.PENDENTE,
    Pedido.Status.EM_SEPARACAO,
    Pedido.Status.FATURADO,
    Pedido.Status.CONCLUIDO,
]


def _versao_termos(empresa):
    base = (empresa.termos_uso or "").strip() + "|" + (empresa.politica_privacidade or "").strip()
    if not base.strip("|"):
        return "v0"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:12]


class Command(BaseCommand):
    help = (
        "Popula dados de demonstração (empresas, equipe, modelos, SKUs e pedidos) "
        "para testes. Idempotente."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default=PASSWORD_PADRAO,
            help=f"Senha dos usuários demo (padrão: {PASSWORD_PADRAO}).",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Remove os dados demo existentes antes de recriar.",
        )

    def handle(self, *args, **options):
        self.password = options["password"]
        self.slugs = [e["slug"] for e in EMPRESAS]

        self.stdout.write("Garantindo planos padrão...")
        call_command("seed_planos")

        if options["reset"]:
            self._resetar()

        with transaction.atomic():
            for dados in EMPRESAS:
                self._criar_empresa(dados)

        self._resumo()

    # ──────────────────────────────────────────────────────────────────────
    def _resetar(self):
        self.stdout.write(self.style.WARNING("Removendo dados de demonstração..."))
        empresas = Empresa.objects.filter(slug__in=self.slugs)
        Pedido.objects.filter(empresa__in=empresas).delete()
        empresas.delete()
        Usuario.objects.filter(username__in=self._usernames()).delete()

    def _usernames(self):
        return [u[0] for e in EMPRESAS for u in e["equipe"]]

    def _criar_empresa(self, dados):
        plano = Plano.objects.get(nome=dados["plano"])
        empresa, criada = Empresa.objects.update_or_create(
            cnpj=dados["cnpj"],
            defaults={
                "nome_fantasia": dados["nome_fantasia"],
                "slug": dados["slug"],
                "email": dados["email"],
                "whatsapp_comercial": dados["whatsapp_comercial"],
                "instagram": dados["instagram"],
                "cor_primaria": dados["cor_primaria"],
                "endereco_origem": dados["endereco_origem"],
                "plano": plano,
                "status": Empresa.Status.ATIVO,
                "termos_uso": TERMOS,
                "politica_privacidade": PRIVACIDADE,
            },
        )
        acao = "criada" if criada else "atualizada"
        self.stdout.write(f"  • Empresa {acao}: {empresa.nome_fantasia} (/{empresa.slug}/)")

        self._criar_equipe(empresa, dados["equipe"])

        modelos = self._criar_modelos(empresa, dados["modelos"])
        if criada:
            self._criar_pedidos(empresa, modelos)

    def _criar_equipe(self, empresa, equipe):
        for username, role, first_name, last_name in equipe:
            usuario, _ = Usuario.objects.get_or_create(
                username=username,
                defaults={"empresa": empresa, "role": role},
            )
            usuario.empresa = empresa
            usuario.role = role
            usuario.first_name = first_name
            usuario.last_name = last_name
            usuario.email = f"{username}@demo.bcmodas.com.br"
            usuario.is_staff = True
            usuario.is_active = True
            usuario.set_password(self.password)
            usuario.save()

    def _criar_modelos(self, empresa, modelos):
        criados = []
        for dados in modelos:
            preco_varejo = Decimal(dados["preco_varejo"])
            preco_atacado = Decimal(dados.get("preco_atacado") or preco_varejo * Decimal("0.80"))
            modelo, _ = Modelo.objects.update_or_create(
                empresa=empresa,
                nome=dados["nome"],
                defaults={
                    "marca": dados["marca"],
                    "preco_varejo": preco_varejo,
                    "preco_atacado": preco_atacado,
                    "qtd_minima_atacado": dados.get("qtd_minima_atacado", 6),
                    "composicao": dados["composicao"],
                    "gramatura": dados["gramatura"],
                    "descricao": dados["descricao"],
                    "tabela_medidas_json": dados["tabela_medidas_json"],
                    "visivel_catalogo": True,
                },
            )
            estoque = dados["estoque_base"]
            for cor_nome, cor_hex in dados["cores"]:
                for tamanho in dados["tamanhos"]:
                    SKU.objects.update_or_create(
                        empresa=empresa,
                        modelo=modelo,
                        cor_nome=cor_nome,
                        tamanho=tamanho,
                        defaults={"cor_hex": cor_hex, "quantidade_estoque": estoque},
                    )
            criados.append(modelo)
        return criados

    def _criar_pedidos(self, empresa, modelos):
        skus = list(
            SKU.objects.filter(empresa=empresa, quantidade_estoque__gt=0).select_related("modelo")
        )
        if not skus:
            return
        versao = _versao_termos(empresa)
        for indice, status in enumerate(STATUS_PEDIDOS):
            cliente = CLIENTES[indice % len(CLIENTES)]
            selecionados = skus[indice : indice + 3] or skus[:2]
            total_itens = 0
            valor_total = Decimal("0")
            pedido = Pedido.objects.create(
                empresa=empresa,
                cliente_nome=cliente[0],
                cliente_documento=cliente[1],
                cliente_whatsapp=cliente[2],
                status=status,
                aceite_lgpd=True,
                ip_aceite="203.0.113.%d" % (10 + indice),
                data_aceite=timezone.now() - timedelta(days=indice + 1),
                versao_termos=versao,
            )
            for sku in selecionados:
                quantidade = (indice % 4) + 1
                preco = sku.modelo.preco_unitario_para(quantidade)
                ItemPedido.objects.create(
                    pedido=pedido,
                    sku=sku,
                    quantidade=quantidade,
                    preco_unitario=preco,
                )
                total_itens += quantidade
                valor_total += preco * quantidade
            pedido.total_itens = total_itens
            pedido.valor_total = valor_total
            pedido.save(update_fields=["total_itens", "valor_total"])

    def _resumo(self):
        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "Seed de demonstração concluído:\n"
                f"  Empresas: {Empresa.objects.count()} | "
                f"Usuários: {Usuario.objects.count()} | "
                f"Modelos: {Modelo.objects.count()} | "
                f"SKUs: {SKU.objects.count()} | "
                f"Pedidos: {Pedido.objects.count()}"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Logins demo (senha '{self.password}'): "
                + ", ".join(self._usernames())
            )
        )
