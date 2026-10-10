from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin

from apps.tenants.mixins import EmpresaScopedAdminMixin
from apps.usuarios.mixins import PerfilAdminMixin

from .models import Cliente


@admin.register(Cliente)
class ClienteAdmin(PerfilAdminMixin, EmpresaScopedAdminMixin, ModelAdmin):
    perfis_negados = ("FINANCEIRO",)
    list_display = (
        "nome_razao_social",
        "tipo_pessoa",
        "cpf_cnpj",
        "whatsapp",
        "email",
        "cidade",
        "estado",
        "is_active",
    )
    list_filter = ("tipo_pessoa", "estado", "is_active")
    search_fields = ("nome_razao_social", "cpf_cnpj", "whatsapp", "email")
    readonly_fields = ("created_at", "updated_at", "last_login")
    fieldsets = (
        (
            _("Identificação"),
            {
                "fields": (
                    "empresa",
                    "nome_razao_social",
                    "tipo_pessoa",
                    "cpf_cnpj",
                    "whatsapp",
                    "email",
                    "is_active",
                )
            },
        ),
        (
            _("Endereço"),
            {
                "fields": (
                    ("cep", "numero"),
                    "endereco",
                    "bairro",
                    ("cidade", "estado"),
                )
            },
        ),
        (_("Auditoria"), {"fields": ("last_login", "created_at", "updated_at")}),
    )

    def save_model(self, request, obj, form, change):
        if not change and not obj.password:
            obj.set_unusable_password()
        super().save_model(request, obj, form, change)
