from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods

from apps.tenants.models import Empresa

from .forms import CadastroClienteForm, LoginClienteForm
from .models import Cliente


def _empresa_ativa(slug):
    empresa = get_object_or_404(Empresa, slug=slug)
    return empresa


def _next_seguro(request, padrao):
    destino = request.POST.get("next") or request.GET.get("next") or ""
    if destino and url_has_allowed_host_and_scheme(
        destino, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return destino
    return padrao


def _redirect_catalogo(slug):
    return redirect(reverse("catalogo_publico", kwargs={"slug": slug}) + "#checkout")


def _contexto_base(request, empresa, **extra):
    from apps.pedidos.views import _url_whatsapp_empresa

    contexto = {
        "empresa": empresa,
        "whatsapp_url": _url_whatsapp_empresa(empresa),
        "cliente_logado": request.user if isinstance(request.user, Cliente) else None,
    }
    contexto.update(extra)
    return contexto


@require_http_methods(["GET", "POST"])
def catalogo_cliente_cadastro(request, slug):
    empresa = _empresa_ativa(slug)
    if empresa.status != Empresa.Status.ATIVO:
        return render(request, "catalogo/indisponivel.html", _contexto_base(request, empresa), status=403)

    if isinstance(request.user, Cliente):
        return _redirect_catalogo(slug)

    form = CadastroClienteForm(request.POST or None, empresa=empresa)
    if request.method == "POST" and form.is_valid():
        cliente = form.save()
        login(request, cliente, backend="apps.clientes.backends.ClienteBackend")
        messages.success(request, _("Cadastro realizado! Você já pode finalizar seu pedido."))
        return redirect(_next_seguro(request, _redirect_catalogo(slug).url))

    return render(
        request,
        "catalogo/acesso.html",
        _contexto_base(
            request,
            empresa,
            aba="cadastro",
            form_cadastro=form,
            form_login=LoginClienteForm(),
        ),
    )


@require_http_methods(["GET", "POST"])
def catalogo_cliente_login(request, slug):
    empresa = _empresa_ativa(slug)
    if empresa.status != Empresa.Status.ATIVO:
        return render(request, "catalogo/indisponivel.html", _contexto_base(request, empresa), status=403)

    if isinstance(request.user, Cliente):
        return _redirect_catalogo(slug)

    form = LoginClienteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        cliente = authenticate(
            request,
            username=form.cleaned_data["email"],
            password=form.cleaned_data["senha"],
        )
        if cliente is not None and isinstance(cliente, Cliente) and cliente.empresa_id == empresa.pk:
            login(request, cliente)
            messages.success(request, _("Bem-vindo de volta!"))
            return redirect(_next_seguro(request, _redirect_catalogo(slug).url))
        if cliente is not None and isinstance(cliente, Cliente):
            messages.error(request, _("Esta conta não pertence a esta loja."))
        else:
            messages.error(request, _("E-mail ou senha inválidos."))

    return render(
        request,
        "catalogo/acesso.html",
        _contexto_base(
            request,
            empresa,
            aba="login",
            form_cadastro=CadastroClienteForm(empresa=empresa),
            form_login=form,
        ),
    )


@require_http_methods(["POST"])
def catalogo_cliente_logout(request, slug):
    empresa = _empresa_ativa(slug)
    logout(request)
    messages.success(request, _("Você saiu da sua conta."))
    return redirect("catalogo_publico", slug=empresa.slug)
