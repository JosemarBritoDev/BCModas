"""Baixa imagens de produtos a partir do Openverse e grava nos campos foto_1..foto_6.

O Openverse (https://openverse.org) agrega imagens de licença livre/aberta.
O comando busca por palavras-chave derivadas do nome e da categoria de cada
Modelo, baixa as fotos compatíveis com uso comercial e salva nos campos de
imagem do produto.

Uso:
    python manage.py popular_imagens_produtos
    python manage.py popular_imagens_produtos --fotos 3
    python manage.py popular_imagens_produtos --limit 10 --force
    python manage.py popular_imagens_produtos --empresa bc-modas

Observação: requer a biblioteca `requests` (ver requirements.txt) e conexão
com a internet. As imagens ficam salvas em MEDIA_ROOT (media/produtos/fotos/).
"""

import requests
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from apps.produtos.models import Modelo

SEARCH_API = "https://api.openverse.org/v1/images/"
USER_AGENT = "BCModas-ImageSeeder/1.0 (+https://bcmodas.com.br)"
TIMEOUT_BUSCA = 30
TIMEOUT_DOWNLOAD = 60

# Quantidade máxima de campos de foto disponíveis no Modelo.
MAX_FOTOS = 6


class Command(BaseCommand):
    help = "Baixa imagens reais (Openverse) para os produtos, salvando em foto_1..foto_6"

    def add_arguments(self, parser):
        parser.add_argument(
            "--fotos",
            type=int,
            default=2,
            help=f"Quantidade de fotos por produto (1 a {MAX_FOTOS}; padrão 2)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Limita a quantidade de produtos processados (0 = todos)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Sobrescreve produtos que já possuem foto_1 preenchida",
        )
        parser.add_argument(
            "--empresa",
            default="",
            help="Slug da empresa; quando informado, processa apenas os produtos dela",
        )

    # ── Busca ────────────────────────────────────────────────────────────────
    def buscar(self, termo):
        """Retorna a lista de resultados de imagem do Openverse para o termo."""
        params = {
            "q": termo,
            "page_size": 10,
            "license_type": "commercial,modification",
            "sort": "relevance",
        }
        try:
            resposta = requests.get(
                SEARCH_API,
                params=params,
                headers={"User-Agent": USER_AGENT},
                timeout=TIMEOUT_BUSCA,
            )
            if resposta.status_code != 200:
                return []
            return resposta.json().get("results", [])
        except requests.RequestException:
            return []

    def termos_busca(self, modelo):
        """Gera termos de busca em ordem de especificidade (do mais ao mais genérico)."""
        categoria = modelo.categoria.nome if modelo.categoria else ""
        primeiro_nome = modelo.nome.split()[0] if modelo.nome else ""
        termos = [
            f"{modelo.nome} {categoria}".strip(),
            f"{modelo.nome} {modelo.marca or ''}".strip(),
            f"{modelo.nome}".strip(),
        ]
        if categoria:
            termos.append(categoria)
        if primeiro_nome and primeiro_nome.lower() != modelo.nome.lower():
            termos.append(f"{primeiro_nome} roupa")
        termos.append("moda roupa")
        # Remove vazios e duplicados preservando a ordem.
        vistos, unicos = set(), []
        for termo in termos:
            if termo and termo not in vistos:
                vistos.add(termo)
                unicos.append(termo)
        return unicos

    # ── Download ─────────────────────────────────────────────────────────────
    def extensao(self, content_type):
        content_type = (content_type or "").lower()
        if "png" in content_type:
            return ".png"
        if "webp" in content_type:
            return ".webp"
        return ".jpg"

    def baixar(self, modelo, url, indice):
        """Baixa a imagem da URL e grava no campo foto_<indice>. Retorna bool."""
        try:
            resposta = requests.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=TIMEOUT_DOWNLOAD,
                allow_redirects=True,
            )
            if resposta.status_code != 200 or not resposta.content:
                return False
            ext = self.extensao(resposta.headers.get("Content-Type"))
            nome = f"{modelo.pk}_{indice}{ext}"
            campo = getattr(modelo, f"foto_{indice}")
            campo.save(nome, ContentFile(resposta.content), save=False)
            return True
        except (requests.RequestException, OSError):
            return False

    def coletar_urls(self, modelo, quantidade):
        """Busca e devolve até `quantidade` URLs válidas para o produto."""
        urls, vistos = [], set()
        for termo in self.termos_busca(modelo):
            for resultado in self.buscar(termo):
                url = resultado.get("url") or resultado.get("thumbnail")
                if url and url not in vistos:
                    vistos.add(url)
                    urls.append(url)
                if len(urls) >= quantidade:
                    return urls
        return urls

    # ── Execução ─────────────────────────────────────────────────────────────
    def handle(self, *args, **options):
        quantidade = max(1, min(options["fotos"], MAX_FOTOS))
        qs = Modelo.objects.select_related("categoria").order_by("pk")
        if options["empresa"]:
            qs = qs.filter(empresa__slug=options["empresa"])
        if not options["force"]:
            qs = qs.filter(foto_1="")
        if options["limit"]:
            qs = qs[: options["limit"]]

        total = qs.count() if hasattr(qs, "count") else len(qs)
        self.stdout.write(f"Processando {total} produto(s) para até {quantidade} foto(s)...")

        processados = 0
        for modelo in qs:
            urls = self.coletar_urls(modelo, quantidade)
            salvas = 0
            for url in urls:
                if salvas >= quantidade:
                    break
                if self.baixar(modelo, url, salvas + 1):
                    salvas += 1

            if salvas:
                modelo.save()
                processados += 1
                self.stdout.write(
                    self.style.SUCCESS(f"[{modelo.pk}] {modelo.nome} -> {salvas} foto(s)")
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f"[{modelo.pk}] {modelo.nome} -> nenhuma foto encontrada")
                )

        self.stdout.write(
            self.style.SUCCESS(f"Concluído: {processados} produto(s) com imagens atualizadas.")
        )
