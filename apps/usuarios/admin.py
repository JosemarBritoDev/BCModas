from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.urls import reverse
from django.utils.html import format_html
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
    readonly_fields = ("link_alterar_senha",)
    fieldsets = (
        (_("Identificação"), {"fields": ("username", "password", "first_name", "last_name", "email")}),
        (_("Permissões de Acesso"), {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        (_("Acesso à Fábrica"), {"fields": ("empresa", "role")}),
        (_("Segurança da Conta"), {"fields": ("link_alterar_senha",)}),
        (_("Datas Importantes"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (_("Acesso à Fábrica"), {"fields": ("empresa", "role")}),
    )

    @admin.display(description=_("Alterar senha"))
    def link_alterar_senha(self, obj):
        if obj is None or not obj.pk:
            return "—"
        url = reverse("admin:auth_user_password_change", args=[obj.pk])
        return format_html(
            '<a class="erp-password-link" href="{}">'
            '<span class="material-symbols-outlined">lock</span>{}</a>',
            url,
            _("Alterar senha deste usuário"),
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