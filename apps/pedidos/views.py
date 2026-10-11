import hashlib
import re
from decimal import Decimal
from urllib.parse import quote

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.clientes.models import Cliente
from apps.financeiro.models import ContaReceber
from apps.financeiro.services import criar_conta_receber_para_pedido
from apps.pedidos.models import ItemPedido, Pedido
from apps.pedidos.services import EstoqueInsuficiente, reservar_estoque
from apps.produtos.models import Categoria, Modelo, SKU
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


def _fmt_brl(valor):
    """Formata um valor Decimal/float no padrão brasileiro (1.234,56)."""
    return f"{Decimal(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _cliente_autenticado(request):
    """Retorna o ``Cliente`` do catálogo autenticado na sessão, se houver."""
    user = getattr(request, "user", None)
    if user is not None and isinstance(user, Cliente):
        return user
    return None


def _redirect_checkout(slug):
    return redirect(reverse("catalogo_publico", kwargs={"slug": slug}) + "#checkout")


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
        f"| {item.sku.tamanho} — R$ {_fmt_brl(item.subtotal)}"
        for item in pedido.itens.select_related("sku__modelo")
    ]

    if pedido.tipo_entrega == Pedido.TipoEntrega.ENTREGA:
        if pedido.endereco_entrega:
            entrega = f"Entrega: {pedido.endereco_entrega}"
        else:
            entrega = "Entrega: endereço a confirmar"
        if pedido.taxa_entrega and pedido.taxa_entrega > 0:
            entrega += f" | Taxa: R$ {_fmt_brl(pedido.taxa_entrega)}"
            total_final = pedido.valor_total_com_frete
        else:
            entrega += " | Taxa: a combinar"
            total_final = pedido.valor_total
    else:
        entrega = "Entrega: Retirada no Local (Grátis)"
        total_final = pedido.valor_total

    texto = [
        f"NOVO PEDIDO — {empresa.nome_fantasia}",
        f"Pedido #{pedido.pk}",
        "",
        "ITENS:",
        *linhas,
        "",
        f"TOTAL: R$ {_fmt_brl(total_final)} "
        f"({pedido.total_itens} {'item' if pedido.total_itens == 1 else 'itens'})",
        "",
        "FORMA DE PAGAMENTO:",
        pedido.get_forma_pagamento_display() or "A definir",
        "",
        entrega,
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

    modelo_filtro = request.GET.get("categoria", "").strip().lower()
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

    if modelo_filtro == "lancamentos":
        modelos = modelos.filter(lancamento=True)
    elif modelo_filtro == "atacado":
        modelos = modelos.filter(preco_atacado__gt=Decimal("0"))
    elif modelo_filtro:
        modelos = modelos.filter(
            categoria__empresa=empresa, categoria__slug=modelo_filtro
        )

    categoria_atual = modelo_filtro
    categorias = _menu_categorias(empresa, categoria_atual)

    termo_busca = request.GET.get("q", "").strip()
    if termo_busca:
        modelos = modelos.filter(
            Q(nome__icontains=termo_busca) | Q(marca__icontains=termo_busca)
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
                "avaliacao": float(modelo.avaliacao or 0),
            }
        )

    contexto = {
        "empresa": empresa,
        "catalogo_itens": catalogo_itens,
        "catalogo_json": catalogo_json,
        "categorias": categorias,
        "categoria_atual": categoria_atual,
        "termo_busca": termo_busca,
        "total_modelos": modelos.count(),
        "tamanhos_ordenados": tamanhos_ordenados,
        "whatsapp_url": _url_whatsapp_empresa(empresa),
        "cliente_logado": _cliente_autenticado(request),
    }
    return render(request, "catalogo/index.html", contexto)


def _menu_categorias(empresa, categoria_atual):
    """Monta o menu horizontal de categorias do catálogo público.

    As categorias são carregadas dinamicamente do modelo ``Categoria``,
    exibindo apenas aquelas que possuem produtos ativos (visíveis) vinculados.
    """
    base = reverse("catalogo_publico", kwargs={"slug": empresa.slug})
    itens = [{"slug": "", "label": "Todos", "url": base, "ativo": not categoria_atual}]

    lancamentos = Modelo.objects.filter(
        empresa=empresa, visivel_catalogo=True, lancamento=True
    ).exists()
    atacado = Modelo.objects.filter(
        empresa=empresa, visivel_catalogo=True, preco_atacado__gt=0
    ).exists()

    especiais = []
    if lancamentos:
        especiais.append(("lancamentos", "Lançamentos"))
    if atacado:
        especiais.append(("atacado", "Atacado"))

    for slug, label in especiais:
        itens.append(
            {
                "slug": slug,
                "label": label,
                "url": f"{base}?categoria={slug}",
                "ativo": categoria_atual == slug,
            }
        )

    categorias = (
        Categoria.objects.filter(empresa=empresa, ativo=True)
        .annotate(
            num_produtos=Count(
                "produtos", filter=Q(produtos__visivel_catalogo=True), distinct=True
            )
        )
        .filter(num_produtos__gt=0)
        .order_by("ordem", "nome")
    )

    for categoria in categorias:
        itens.append(
            {
                "slug": categoria.slug,
                "label": categoria.nome,
                "total": categoria.num_produtos,
                "url": f"{base}?categoria={categoria.slug}",
                "ativo": categoria_atual == categoria.slug,
            }
        )
    return itens


@require_http_methods(["POST"])
def catalogo_checkout(request, slug):
    empresa = get_object_or_404(Empresa, slug=slug)

    if empresa.status != Empresa.Status.ATIVO:
        raise Http404("Catálogo não disponível")

    cliente = _cliente_autenticado(request)
    if cliente is None or cliente.empresa_id != empresa.pk:
        messages.info(
            request,
            "Faça login ou cadastre-se para finalizar seu pedido.",
        )
        destino = reverse("catalogo_publico", kwargs={"slug": slug}) + "#checkout"
        return redirect(
            reverse("catalogo_cliente_login", kwargs={"slug": slug})
            + f"?next={quote(destino)}"
        )

    aceite = request.POST.get("aceite_lgpd") == "on"
    if not aceite:
        messages.error(request, "É necessário aceitar os Termos de Uso e Política de Privacidade.")
        return _redirect_checkout(slug)

    forma_raw = (request.POST.get("forma_pagamento") or "").upper()
    forma_pagamento = (
        forma_raw
        if forma_raw in Pedido.FormaPagamento.values
        else Pedido.FormaPagamento.PIX
    )

    entrega_raw = (request.POST.get("tipo_entrega") or "").upper()
    tipo_entrega = (
        entrega_raw
        if entrega_raw in Pedido.TipoEntrega.values
        else Pedido.TipoEntrega.RETIRADA_LOCAL
    )

    endereco_entrega = ""
    taxa_entrega = Decimal("0.00")
    if tipo_entrega == Pedido.TipoEntrega.ENTREGA:
        endereco_entrega = (request.POST.get("endereco_entrega") or "").strip()
        if not endereco_entrega:
            messages.error(request, "Informe o endereço de entrega para finalizar o pedido.")
            return _redirect_checkout(slug)
        taxa_entrega = empresa.taxa_entrega_padrao or Decimal("0.00")

    sku_ids = []
    for key in request.POST.keys():
        if key.startswith("qty_"):
            m = re.match(r"qty_(\d+)$", key)
            if m:
                sku_ids.append(int(m.group(1)))

    if not sku_ids:
        messages.error(request, "Selecione pelo menos um item para finalizar o pedido.")
        return _redirect_checkout(slug)

    skus_selecionados = SKU.objects.select_related("modelo").filter(
        empresa=empresa,
        modelo__empresa=empresa,
        modelo__visivel_catalogo=True,
        pk__in=sku_ids,
    )
    skus_map = {s.pk: s for s in skus_selecionados}

    itens_detalhados = []
    itens_estoque = []
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
            return _redirect_checkout(slug)
        preco = s.modelo.preco_unitario_para(qtd)
        subtotal = preco * qtd
        itens_detalhados.append((s, qtd, preco))
        itens_estoque.append((s.pk, qtd))
        total_itens += qtd
        valor_total += subtotal

    if not itens_detalhados:
        messages.error(request, "Nenhum item com quantidade válida foi selecionado.")
        return _redirect_checkout(slug)

    versao_termos = _versao_termos_empresa(empresa)

    try:
        with transaction.atomic():
            reservar_estoque(itens_estoque)
            pedido = Pedido.objects.create(
                empresa=empresa,
                cliente=cliente,
                cliente_nome=cliente.nome_razao_social,
                cliente_documento=cliente.cpf_cnpj,
                cliente_whatsapp=cliente.whatsapp,
                total_itens=total_itens,
                valor_total=valor_total,
                status=Pedido.Status.AGUARDANDO_PAGAMENTO,
                status_financeiro=Pedido.StatusFinanceiro.AGUARDANDO_PAGAMENTO,
                forma_pagamento=forma_pagamento,
                tipo_entrega=tipo_entrega,
                endereco_entrega=endereco_entrega,
                taxa_entrega=taxa_entrega,
                aceite_lgpd=True,
                ip_aceite=_get_client_ip(request),
                data_aceite=timezone.now(),
                versao_termos=versao_termos,
            )
            ItemPedido.objects.bulk_create(
                [
                    ItemPedido(pedido=pedido, sku=s, quantidade=qtd, preco_unitario=preco)
                    for s, qtd, preco in itens_detalhados
                ]
            )
            forma_conta = {
                "PIX": ContaReceber.FormaPagamento.PIX,
                "CREDITO": ContaReceber.FormaPagamento.CARTAO,
                "DEBITO": ContaReceber.FormaPagamento.CARTAO,
            }.get(forma_pagamento, ContaReceber.FormaPagamento.PIX)
            criar_conta_receber_para_pedido(pedido, forma_pagamento=forma_conta)
    except EstoqueInsuficiente as exc:
        messages.error(
            request,
            f"Estoque insuficiente para {exc.sku}. Disponível: {exc.disponivel}.",
        )
        return _redirect_checkout(slug)

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


@require_http_methods(["GET"])
def catalogo_legal(request, slug):
    """Página institucional de Termos de Uso e Política de Privacidade (LGPD)."""
    empresa = get_object_or_404(Empresa, slug=slug)
    if empresa.status != Empresa.Status.ATIVO:
        raise Http404("Catálogo não disponível")

    contexto = {
        "empresa": empresa,
        "whatsapp_url": _url_whatsapp_empresa(empresa),
        "cliente_logado": _cliente_autenticado(request),
    }
    return render(request, "catalogo/legal.html", contexto)
