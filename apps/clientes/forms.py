import re

from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Cliente

_INPUT = (
    "w-full rounded-xl border border-slate-200 px-3.5 py-2.5 text-sm outline-none "
    "transition focus:border-brand focus:ring-2 focus:ring-brand/20"
)


class CadastroClienteForm(forms.ModelForm):
    """Cadastro do comprador no catálogo público."""

    senha = forms.CharField(
        label=_("Senha"),
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        min_length=6,
    )
    senha_confirma = forms.CharField(
        label=_("Confirmar senha"),
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    class Meta:
        model = Cliente
        fields = (
            "nome_razao_social",
            "tipo_pessoa",
            "cpf_cnpj",
            "whatsapp",
            "email",
            "cep",
            "endereco",
            "numero",
            "bairro",
            "cidade",
            "estado",
        )
        widgets = {name: forms.TextInput(attrs={"class": _INPUT}) for name in fields}
        widgets["tipo_pessoa"] = forms.Select(attrs={"class": _INPUT})
        widgets["estado"] = forms.Select(attrs={"class": _INPUT})
        widgets["email"] = forms.EmailInput(attrs={"class": _INPUT})

    def __init__(self, *args, empresa=None, **kwargs):
        self.empresa = empresa
        super().__init__(*args, **kwargs)

    def clean_email(self):
        email = (self.cleaned_data["email"] or "").strip().lower()
        if Cliente.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(_("Já existe uma conta com este e-mail."))
        return email

    def clean_cpf_cnpj(self):
        valor = re.sub(r"\D", "", self.cleaned_data.get("cpf_cnpj") or "")
        return valor

    def clean_whatsapp(self):
        return re.sub(r"\D", "", self.cleaned_data.get("whatsapp") or "")

    def clean_cep(self):
        return re.sub(r"\D", "", self.cleaned_data.get("cep") or "")

    def clean(self):
        dados = super().clean()
        if dados.get("senha") and dados.get("senha") != dados.get("senha_confirma"):
            self.add_error("senha_confirma", _("As senhas não conferem."))
        return dados

    def save(self, commit=True):
        cliente = super().save(commit=False)
        cliente.empresa = self.empresa
        cliente.set_password(self.cleaned_data["senha"])
        if commit:
            cliente.save()
        return cliente


class LoginClienteForm(forms.Form):
    """Login do comprador (e-mail + senha)."""

    email = forms.EmailField(
        label=_("E-mail"),
        widget=forms.EmailInput(attrs={"class": _INPUT, "autocomplete": "email"}),
    )
    senha = forms.CharField(
        label=_("Senha"),
        widget=forms.PasswordInput(attrs={"class": _INPUT, "autocomplete": "current-password"}),
    )
