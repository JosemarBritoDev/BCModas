from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin

from .models import Empresa, Plano


@admin.register(Plano)
class PlanoAdmin(ModelAdmin):
    list_display = ("nome", "preco_mensal", "limite_usuarios", "limite_produtos")
    search_fields = ("nome",)
    ordering = ("preco_mensal",)
    readonly_fields = ("created_at", "updated_at")

    def has_module_permission(self, request):
        return self._is_superadmin(request)

    def has_view_permission(self, request, obj=None):
        return self._is_superadmin(request)

    def has_add_permission(self, request):
        return self._is_superadmin(request)

    def has_delete_permission(self, request, obj=None):
        return self._is_superadmin(request)

    @staticmethod
    def _is_superadmin(request):
        return request.user.is_superuser or getattr(
            request.user, "role", None
        ) == "SUPERADMIN"


@admin.register(Empresa)
class EmpresaAdmin(ModelAdmin):
    list_display = ("nome_fantasia", "cnpj", "plano", "status")
    list_filter = ("status", "plano")
    search_fields = ("nome_fantasia", "cnpj", "email")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (_("Dados da Empresa"), {
            "fields": (
                "nome_fantasia",
                "cnpj",
                "email",
                "whatsapp_comercial",
                "instagram",
                "endereco_origem",
            )
        }),
        (_("Identidade Visual"), {"fields": ("logo", "favicon")}),
        (_("Assinatura"), {"fields": ("plano", "status")}),
        (_("Documentos Legais"), {"fields": ("termos_uso", "politica_privacidade")}),
        (_("Auditoria"), {"fields": ("created_at", "updated_at")}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser or getattr(
            request.user, "role", None
        ) == "SUPERADMIN":
            return qs
        empresa_id = getattr(request.user, "empresa_id", None)
        if not empresa_id:
            return qs.none()
        return qs.filter(pk=empresa_id)

    def get_readonly_fields(self, request, obj=None):
        readonly = list(self.readonly_fields)
        if not request.user.is_superuser and getattr(
            request.user, "role", None
        ) != "SUPERADMIN":
            readonly += ["plano", "status", "cnpj"]
        return readonly