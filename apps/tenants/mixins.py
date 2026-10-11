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
            if empresa is None:
                # Superusuário sem empresa vinculada: usa a fábrica única
                # (mono-empresa) para não gravar registros órfãos.
                from apps.tenants.models import Empresa

                empresa = Empresa.obter_fabrica()
            if empresa is not None:
                obj.empresa = empresa
        super().save_model(request, obj, form, change)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Restringe e pré-seleciona a empresa do usuário.

        Perfis não-superadmin só podem vincular registros à própria fábrica.
        Como o ERP é mono-empresa, o seletor já vem preenchido com a fábrica
        única, evitando o erro de "campo obrigatório" no cadastro.
        """
        formfield = super().formfield_for_foreignkey(db_field, request, **kwargs)
        if db_field.name != self.empresa_lookup or formfield is None:
            return formfield

        user = getattr(request, "user", None)
        is_super = bool(
            user is not None
            and (
                getattr(user, "is_superuser", False)
                or getattr(user, "role", None) == "SUPERADMIN"
            )
        )
        empresa = getattr(user, "empresa", None)

        if not is_super and empresa is not None:
            formfield.queryset = formfield.queryset.filter(pk=empresa.pk)

        if empresa is None:
            from apps.tenants.models import Empresa

            empresa = Empresa.obter_fabrica()

        if empresa is not None:
            formfield.initial = empresa.pk
        return formfield
