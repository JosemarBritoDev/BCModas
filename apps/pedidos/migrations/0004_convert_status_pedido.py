from django.db import migrations


# Converte os status antigos do pedido para o novo fluxo com trava financeira.
STATUS_MAP = {
    "PENDENTE": ("AGUARDANDO_PAGAMENTO", "AGUARDANDO_PAGAMENTO"),
    "EM_SEPARACAO": ("EM_SEPARACAO", "PAGO_LIBERADO"),
    "FATURADO": ("PAGO_LIBERADO", "FATURADO_ATACADO"),
    "ENVIADO": ("ENVIADO", "PAGO_LIBERADO"),
    "CONCLUIDO": ("CONCLUIDO", "PAGO_LIBERADO"),
}


def forwards(apps, schema_editor):
    Pedido = apps.get_model("pedidos", "Pedido")
    for status_antigo, (status_novo, financeiro) in STATUS_MAP.items():
        Pedido.objects.filter(status=status_antigo).update(
            status=status_novo, status_financeiro=financeiro
        )


def backwards(apps, schema_editor):
    Pedido = apps.get_model("pedidos", "Pedido")
    for status_antigo, (status_novo, financeiro) in STATUS_MAP.items():
        Pedido.objects.filter(status=status_novo).update(status=status_antigo)
    Pedido.objects.update(status_financeiro="AGUARDANDO_PAGAMENTO")


class Migration(migrations.Migration):
    dependencies = [
        ("pedidos", "0003_pedido_status_financeiro_alter_pedido_status"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
