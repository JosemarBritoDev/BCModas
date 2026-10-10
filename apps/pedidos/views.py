import hashlib
import re
from decimal import Decimal
from urllib.parse import quote

from django.contrib import messages
from django.db import transaction
from django.db.models import Prefetch
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.pedidos.models import ItemPedido, Pedido
from apps.produtos.models import Modelo, SKU
from apps.tenants.models import Empresa


def _get_client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR") or None


def _only_digits(value):
    if not value:
        return ""
    return re.sub(r"\D", "", str(value))


def _versao_termos_empresa(empresa):
    if not empresa:
        return "v0"
    base = (empresa.termos_uso or "").strip() + "|" + (empresa.politica_privacidade or "").strip()
    if not base:
        return "v0"
    sha = hashlib.sha256(base.encode("utf-8")).hexdigest()
    return sha[:12]


def _formatar_numero_whatsapp(empresa_whatsapp):
    digitos = _only_digits(empresa_whatsapp)
    if not digitos:
        return ""
    if len(digitos) <= 11:
        digitos = "55" + digitos
    return digitos


def _url_whatsapp_empresa(empresa):
    numero = _formatar_numero_whatsapp(empresa.whatsapp_comercial)
    return f"https://wa.me/{numero}" if numero else ""


def _montar_payload_whatsapp(empresa, pedido):
    linhas = [
        f"• {item.quantidade}x {item.sku.modelo.nome} | {item.sku.cor_nome} "
        f"| {item.sku.tamanho} — R$ {item.subtotal:,.2f}"
        for item in pedido.itens.select_related("sku__modelo")
    ]
    texto = [
        f"NOVO PEDIDO — {empresa.nome_fantasia}",
        f"Pedido #{pedido.pk}",
        "",
        "ITENS:",
        *linhas,
        "",
        f"TOTAL: R$ {pedido.valor_total:,.2f} "
        f"({pedido.total_itens} {'item' if pedido.total_itens == 1 else 'itens'})",
        "",
        f"Cliente: {pedido.cliente_nome}",
    ]
    if pedido.cliente_documento:
        texto.append(f"Documento: {pedido.cliente_documento}")
    texto.append(f"WhatsApp: {pedido.cliente_whatsapp}")
    texto.append("")
    texto.append("Aceite LGPD: Sim")
    texto.append(f"Versão dos termos: {pedido.versao_termos}")
    texto.append("")
    texto.append("Solicito retorno para confirmação e prazo de entrega.")

    numero = (
        _formatar_numero_whatsapp(empresa.whatsapp_comercial)
        or _only_digits(empresa.whatsapp_comercial)
        or "0000000000"
    )
    return f"https://wa.me/{numero}?text={quote(chr(10).join(texto))}"


@require_http_methods(["GET"])
def catalogo_home(request):
    """Redireciona a raiz para a vitrine da fábrica ativa (operação mono-empresa)."""
    empresa = (
        Empresa.objects.filter(status=Empresa.Status.ATIVO).order_by("pk").first()
    )
    if not empresa:
        raise Http404("Nenhuma fábrica ativa configurada")
    return redirect("catalogo_publico", slug=empresa.slug)


@require_http_methods(["GET"])
def catalogo_publico(request, slug):
    empresa = get_object_or_404(Empresa, slug=slug)

    if empresa.status != Empresa.Status.ATIVO:
        return render(
            request,
            "catalogo/indisponivel.html",
            {"empresa": empresa, "whatsapp_url": _url_whatsapp_empresa(empresa)},
            status=403,
        )

    tamanhos_ordenados = [t[0] for t in SKU.Tamanho.choices]

    modelos = (
        Modelo.objects.filter(empresa=empresa, visivel_catalogo=True)
        .prefetch_related(
            Prefetch(
                "skus",
                queryset=SKU.objects.filter(empresa=empresa).order_by(
                    "cor_nome", "tamanho"
                ),
            )
        )
        .order_by("nome")
    )

    catalogo_itens = []
    for modelo in modelos:
        fotos = []
        for i in range(1, 7):
            img = getattr(modelo, f"foto_{i}")
            if img:
                fotos.append(img.url)

        skus = list(modelo.skus.all())
        cor_map = {}
        cor_ordem = []
        for s in skus:
            key = s.cor_nome
            if key not in cor_map:
                cor_map[key] = {"hex": s.cor_hex or "#000000", "itens": {}}
                cor_ordem.append(key)
            cor_map[key]["itens"][s.tamanho] = s

        tamanhos = [t for t in tamanhos_ordenados if any(t in cor_map[c]["itens"] for c in cor_ordem)]

        cores = []
        for c in cor_ordem:
            data = cor_map[c]
            celulas = [data["itens"].get(t) for t in tamanhos]
            cores.append({"nome": c, "hex": data["hex"], "celulas": celulas})

        catalogo_itens.append(
            {
                "modelo": modelo,
                "fotos": fotos,
                "cores": cores,
                "tamanhos": tamanhos,
                "preco_varejo": modelo.preco_varejo,
                "preco_atacado": modelo.preco_atacado if modelo.tem_atacado else None,
                "qtd_minima_atacado": modelo.qtd_minima_atacado,
            }
        )

    catalogo_json = []
    for item in catalogo_itens:
        modelo = item["modelo"]
        cores_json = []
        for cor in item["cores"]:
            skus = [
                {"id": cell.pk, "tamanho": cell.tamanho, "estoque": cell.quantidade_estoque}
                for cell in cor["celulas"]
                if cell is not None
            ]
            cores_json.append({"nome": cor["nome"], "hex": cor["hex"], "skus": skus})
        catalogo_json.append(
            {
                "id": modelo.pk,
                "nome": modelo.nome,
                "marca": modelo.marca,
                "fotos": item["fotos"],
                "preco_varejo": float(modelo.preco_varejo),
                "preco_atacado": float(modelo.preco_atacado) if modelo.tem_atacado else None,
                "qtd_minima_atacado": modelo.qtd_minima_atacado,
                "cores": cores_json,
            }
        )

    contexto = {
        "empresa": empresa,
        "catalogo_itens": catalogo_itens,
        "catalogo_json": catalogo_json,
        "tamanhos_ordenados": tamanhos_ordenados,
        "whatsapp_url": _url_whatsapp_empresa(empresa),
    }
    return render(request, "catalogo/index.html", contexto)


@require_http_methods(["POST"])
def catalogo_checkout(request, slug):
    empresa = get_object_or_404(Empresa, slug=slug)

    if empresa.status != Empresa.Status.ATIVO:
        raise Http404("Catálogo não disponível")

    cliente_nome = (request.POST.get("cliente_nome") or "").strip()
    cliente_documento = (request.POST.get("cliente_documento") or "").strip()
    cliente_whatsapp = (request.POST.get("cliente_whatsapp") or "").strip()
    aceite = request.POST.get("aceite_lgpd") == "on"

    if not cliente_nome:
        messages.error(request, "Informe o nome do cliente.")
        return redirect(reverse("catalogo_publico", kwargs={"slug": slug}) + "#checkout")

    if not cliente_whatsapp:
        messages.error(request, "Informe o WhatsApp do cliente.")
        return redirect(reverse("catalogo_publico", kwargs={"slug": slug}) + "#checkout")

    if not aceite:
        messages.error(request, "É necessário aceitar os Termos de Uso e Política de Privacidade.")
        return redirect(reverse("catalogo_publico", kwargs={"slug": slug}) + "#checkout")

    sku_ids = []
    for key in request.POST.keys():
        if key.startswith("qty_"):
            m = re.match(r"qty_(\d+)$", key)
            if m:
                sku_ids.append(int(m.group(1)))

    if not sku_ids:
        messages.error(request, "Selecione pelo menos um item para finalizar o pedido.")
        return redirect(reverse("catalogo_publico", kwargs={"slug": slug}) + "#checkout")

    skus_selecionados = SKU.objects.select_related("modelo").filter(
        empresa=empresa,
        modelo__empresa=empresa,
        modelo__visivel_catalogo=True,
        pk__in=sku_ids,
    )
    skus_map = {s.pk: s for s in skus_selecionados}

    itens_detalhados = []
    total_itens = 0
    valor_total = Decimal("0")

    for sid in sku_ids:
        s = skus_map.get(sid)
        if not s:
            continue
        qtd_str = request.POST.get(f"qty_{sid}") or "0"
        try:
            qtd = int(qtd_str)
        except ValueError:
            qtd = 0
        if qtd <= 0:
            continue
        if s.quantidade_estoque < qtd:
            messages.error(
                request,
                f"Quantidade indisponível para {s.modelo.nome} | {s.cor_nome} | {s.tamanho}. Estoque: {s.quantidade_estoque}",
            )
            return redirect(reverse("catalogo_publico", kwargs={"slug": slug}) + "#checkout")
        preco = s.modelo.preco_unitario_para(qtd)
        subtotal = preco * qtd
        itens_detalhados.append((s, qtd, preco, subtotal))
        total_itens += qtd
        valor_total += subtotal

    if not itens_detalhados:
        messages.error(request, "Nenhum item com quantidade válida foi selecionado.")
        return redirect(reverse("catalogo_publico", kwargs={"slug": slug}) + "#checkout")

    versao_termos = _versao_termos_empresa(empresa)

    with transaction.atomic():
        pedido = Pedido.objects.create(
            empresa=empresa,
            cliente_nome=cliente_nome,
            cliente_documento=cliente_documento,
            cliente_whatsapp=cliente_whatsapp,
            total_itens=total_itens,
            valor_total=valor_total,
            status=Pedido.Status.PENDENTE,
            aceite_lgpd=True,
            ip_aceite=_get_client_ip(request),
            data_aceite=timezone.now(),
            versao_termos=versao_termos,
        )
        for s, qtd, preco, subtotal in itens_detalhados:
            ItemPedido.objects.create(
                pedido=pedido,
                sku=s,
                quantidade=qtd,
                preco_unitario=preco,
            )

    _registrar_pedido_na_sessao(request, pedido.pk)

    return redirect(
        reverse(
            "catalogo_pedido_enviado",
            kwargs={"slug": slug, "pedido_id": pedido.pk},
        )
    )


def _registrar_pedido_na_sessao(request, pedido_id):
    pedidos = request.session.get("pedidos_catalogo", [])
    if pedido_id not in pedidos:
        pedidos.append(pedido_id)
    request.session["pedidos_catalogo"] = pedidos[-20:]


@require_http_methods(["GET"])
def catalogo_pedido_enviado(request, slug, pedido_id):
    empresa = get_object_or_404(Empresa, slug=slug)

    if pedido_id not in request.session.get("pedidos_catalogo", []):
        raise Http404("Pedido não encontrado")

    pedido = get_object_or_404(Pedido, pk=pedido_id, empresa=empresa)

    wa_url = _montar_payload_whatsapp(empresa, pedido) if pedido.aceite_lgpd else ""

    contexto = {
        "empresa": empresa,
        "pedido": pedido,
        "wa_url": wa_url,
        "whatsapp_url": _url_whatsapp_empresa(empresa),
    }
    return render(request, "catalogo/sucesso.html", contexto)
