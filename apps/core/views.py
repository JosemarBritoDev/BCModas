"""Views do núcleo do ERP (Assistente Silk)."""

import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .services.help_assistant import HelpAssistantService


def _extrair_payload(request):
    """Aceita tanto formulário quanto JSON no corpo da requisição."""
    if request.content_type == "application/json":
        try:
            return json.loads(request.body or b"{}")
        except (ValueError, TypeError):
            return {}
    return request.POST


@login_required
@require_POST
def silk_help(request):
    """Endpoint do chat do Silk: recebe a pergunta e a rota atual."""
    payload = _extrair_payload(request)
    pergunta = (payload.get("pergunta") or "").strip()
    rota = (payload.get("rota") or "").strip()

    if not pergunta:
        return JsonResponse(
            {
                "resposta": "Me pergunte algo sobre o sistema que eu te ajudo!",
                "bloqueado": False,
                "modulo": None,
                "fonte": None,
            },
            status=400,
        )

    resultado = HelpAssistantService(request.user, rota).responder(pergunta)
    return JsonResponse(resultado, json_dumps_params={"ensure_ascii": False})
