from django.contrib.auth.backends import ModelBackend

from .models import Cliente


class ClienteBackend(ModelBackend):
    """Autentica clientes do catálogo pelo e-mail e senha.

    Convive com o ``ModelBackend`` (usuários internos do ERP), permitindo que
    a mesma instância Django suporte duas bases de usuários distintas sem
    compartilhar permissões.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        email = username or kwargs.get("email")
        if email is None or password is None:
            return None
        try:
            cliente = Cliente.objects.get(email__iexact=email)
        except Cliente.DoesNotExist:
            Cliente().set_password(password)
            return None
        if cliente.check_password(password) and self.user_can_authenticate(cliente):
            return cliente
        return None

    def get_user(self, user_id):
        try:
            return Cliente.objects.get(pk=user_id)
        except Cliente.DoesNotExist:
            return None
