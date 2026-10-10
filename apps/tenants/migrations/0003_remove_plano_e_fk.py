from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0002_empresa_cor_primaria_empresa_slug"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="empresa",
            name="plano",
        ),
        migrations.DeleteModel(
            name="Plano",
        ),
        migrations.AlterModelOptions(
            name="empresa",
            options={
                "ordering": ["nome_fantasia"],
                "verbose_name": "Dados da Confecção",
                "verbose_name_plural": "Dados da Confecção",
            },
        ),
    ]
