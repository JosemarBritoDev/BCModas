from django.utils.translation import gettext_lazy as _


class EmpresaScopedAdminMixin:
    """Isola o admin por empresa.

    Superadmins enxergam todos os registros. Demais perfis enxergam
    apenas os registros da própria fábrica.
    """

    empresa_lookup = "empresa"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        user = request.user
        if user.is_superuser or getattr(user, "role", None) == "SUPERADMIN":
            return qs
        empresa_id = getattr(user, "empresa_id", None)
        if not empresa_id:
            return qs.none()
        return qs.filter(**{f"{self.empresa_lookup}_id": empresa_id})

    def save_model(self, request, obj, form, change):
        if not getattr(obj, "empresa_id", None):
            empresa = getattr(request.user, "empresa", None)
            if empresa is not None:
                obj.empresa = empresa
        super().save_model(request, obj, form, change)