from decimal import Decimal

from django.db import migrations, models


def migrar_precos_existentes(apps, schema_editor):
    """Preenche o preço de atacado dos modelos que ainda não possuem valor."""
    Modelo = apps.get_model("produtos", "Modelo")
    for modelo in Modelo.objects.all():
        if not modelo.preco_atacado:
            modelo.preco_atacado = (modelo.preco_varejo or Decimal("0.00")) * Decimal("0.85")
            modelo.save(update_fields=["preco_atacado"])


class Migration(migrations.Migration):

    dependencies = [
        ("produtos", "0001_initial"),
    ]

    operations = [
        migrations.RenameField(
            model_name="modelo",
            old_name="preco_tabela",
            new_name="preco_varejo",
        ),
        migrations.AlterField(
            model_name="modelo",
            name="preco_varejo",
            field=models.DecimalField(
                decimal_places=2,
                help_text="Valor da peça avulsa (venda no varejo).",
                max_digits=10,
                verbose_name="Preço Varejo",
            ),
        ),
        migrations.AddField(
            model_name="modelo",
            name="preco_atacado",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                help_text="Valor promocional por peça a partir da quantidade mínima de atacado.",
                max_digits=10,
                verbose_name="Preço Atacado",
            ),
        ),
        migrations.AddField(
            model_name="modelo",
            name="qtd_minima_atacado",
            field=models.PositiveIntegerField(
                default=6,
                help_text="Quantidade mínima do item para aplicar o preço de atacado.",
                verbose_name="Qtd. Mínima Atacado",
            ),
        ),
        migrations.RunPython(migrar_precos_existentes, migrations.RunPython.noop),
    ]
