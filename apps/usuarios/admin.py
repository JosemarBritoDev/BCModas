from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin

from .mixins import PerfilAdminMixin
from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(PerfilAdminMixin, BaseUserAdmin, ModelAdmin):
    perfis_permitidos = ("SUPERADMIN", "GERENTE")
    list_display = ("username", "email", "first_name", "empresa", "role", "is_active")
    list_filter = ("role", "is_active", "is_staff", "empresa")
    search_fields = ("username", "email", "first_name", "last_name")
    fieldsets = BaseUserAdmin.fieldsets + (
        (_("Acesso à Fábrica"), {"fields": ("empresa", "role")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (_("Acesso à Fábrica"), {"fields": ("empresa", "role")}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        user = request.user
        if user.is_superuser or getattr(user, "role", None) == "SUPERADMIN":
            return qs
        empresa_id = getattr(user, "empresa_id", None)
        if not empresa_id:
            return qs.none()
        return qs.filter(empresa_id=empresa_id)