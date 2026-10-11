"""RBAC por setor para os ModelAdmin do ERP.

O ERP é mono-empresa e usa perfis de acesso (``Usuario.Role``) em vez das
permissões nativas do Django. Este mixin centraliza a decisão de acesso para
que cada admin informe apenas quais perfis podem enxergá-lo.
"""


class PerfilAdminMixin:
    """Restringe o admin por perfil de acesso (RBAC).

    ``perfis_permitidos``: lista branca de perfis (``None`` libera todos).
    ``perfis_negados``: lista negra de perfis.
    Superusuários do Django sempre têm acesso total.
    """

    perfis_permitidos = None
    perfis_negados = ()

    def _perfil_autorizado(self, request):
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        role = getattr(user, "role", None)
        if self.perfis_permitidos is not None and role not in self.perfis_permitidos:
            return False
        if role in self.perfis_negados:
            return False
        return True

    def _is_auditor(self, request):
        """Indica se o usuário é o perfil somente leitura (Auditor/Visitante).

        Superusuários nunca são tratados como auditores, preservando o acesso
        total do administrador do sistema.
        """
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated or user.is_superuser:
            return False
        return bool(getattr(user, "is_auditor", False))

    # O acesso é decidido exclusivamente pelo perfil (não por permissões
    # nativas do Django), por isso não delegamos ao ``super()``.
    #
    # Auditor/Visitante: enxerga todos os módulos e registros (inclusive os que
    # não estão em ``perfis_permitidos``), porém nunca cria, altera ou exclui.
    def has_module_permission(self, request):
        if self._is_auditor(request):
            return True
        return self._perfil_autorizado(request)

    def has_view_permission(self, request, obj=None):
        if self._is_auditor(request):
            return True
        return self._perfil_autorizado(request)

    def has_add_permission(self, request):
        if self._is_auditor(request):
            return False
        return self._perfil_autorizado(request)

    def has_change_permission(self, request, obj=None):
        if self._is_auditor(request):
            return False
        return self._perfil_autorizado(request)

    def has_delete_permission(self, request, obj=None):
        if self._is_auditor(request):
            return False
        return self._perfil_autorizado(request)
