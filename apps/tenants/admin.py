from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin

from apps.usuarios.mixins import PerfilAdminMixin

from .models import Empresa


@admin.register(Empresa)
class EmpresaAdmin(PerfilAdminMixin, ModelAdmin):
    """Gerenciamento da instância única da fábrica.

    O ERP é mono-empresa: existe apenas o registro da própria confecção.
    A listagem redireciona automaticamente para a edição desse registro.
    """

    perfis_permitidos = ("SUPERADMIN", "GERENTE")

    list_display = ("nome_fantasia", "cnpj", "whatsapp_comercial", "status")
    search_fields = ("nome_fantasia", "slug", "cnpj", "email")
    readonly_fields = ("created_at", "updated_at", "link_catalogo")
    fieldsets = (
        (
            _("Dados da Fábrica"),
            {
                "fields": (
                    "nome_fantasia",
                    "slug",
                    "cnpj",
                    "email",
                    "whatsapp_comercial",
                    "instagram",
                    "endereco_origem",
                    "status",
                )
            },
        ),
        (_("Identidade Visual"), {"fields": ("logo", "favicon", "cor_primaria")}),
        (
            _("Entrega e Frete"),
            {
                "fields": ("taxa_entrega_padrao",),
                "description": _(
                    "Taxa sugerida no checkout quando o cliente escolhe 'Entrega a Combinar'. "
                    "Deixe 0,00 para informar 'a combinar' no WhatsApp."
                ),
            },
        ),
        (
            _("Catálogo Público"),
            {
                "fields": ("link_catalogo",),
                "description": _(
                    "Endereço público da vitrine da fábrica (atacado e varejo)."
                ),
            },
        ),
        (_("Termos LGPD"), {"fields": ("termos_uso", "politica_privacidade")}),
        (_("Auditoria"), {"fields": ("created_at", "updated_at")}),
    )

    @admin.display(description=_("Catálogo Público"))
    def link_catalogo(self, obj):
        if not obj or not obj.slug:
            return "—"
        url = reverse("catalogo_publico", kwargs={"slug": obj.slug})
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">{}</a>', url, url
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

    # ---- Travas de segurança (RBAC) --------------------------------------
    def has_view_permission(self, request, obj=None):
        return self._perfil_autorizado(request) and bool(request.user.is_authenticated)

    def has_change_permission(self, request, obj=None):
        """Somente GERENTE/SUPERADMIN editam dados cadastrais e LGPD."""
        return self._perfil_autorizado(request) and bool(
            getattr(request.user, "is_gerente", False)
        )

    def has_add_permission(self, request):
        """Permite cadastrar a fábrica somente se ainda não existir nenhuma."""
        if not self._perfil_autorizado(request):
            return False
        if not getattr(request.user, "is_gerente", False):
            return False
        return not self.get_queryset(request).exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        """Atalho direto para a edição da fábrica ou para o cadastro inicial."""
        if not self._perfil_autorizado(request):
            raise PermissionDenied
        qs = self.get_queryset(request)
        obj = (
            qs.filter(status=Empresa.Status.ATIVO).order_by("pk").first()
            or qs.order_by("pk").first()
        )
        if obj is not None:
            return HttpResponseRedirect(
                reverse("admin:tenants_empresa_change", args=[obj.pk])
            )
        if self.has_add_permission(request):
            return HttpResponseRedirect(reverse("admin:tenants_empresa_add"))
        return super().changelist_view(request, extra_context)
