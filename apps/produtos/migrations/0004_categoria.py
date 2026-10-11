from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0001_initial"),
        ("produtos", "0003_modelo_avaliacao_modelo_categoria_modelo_lancamento"),
    ]

    operations = [
        migrations.CreateModel(
            name="Categoria",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("nome", models.CharField(max_length=80, verbose_name="Nome")),
                (
                    "slug",
                    models.SlugField(
                        blank=True,
                        help_text="Identificador amigável usado na URL do catálogo.",
                        max_length=90,
                        verbose_name="Slug",
                    ),
                ),
                (
                    "ordem",
                    models.PositiveIntegerField(
                        default=0,
                        help_text="Menor valor aparece primeiro no menu.",
                        verbose_name="Ordem",
                    ),
                ),
                (
                    "ativo",
                    models.BooleanField(
                        default=True,
                        help_text="Categorias inativas não são exibidas.",
                        verbose_name="Ativa",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="Criado em"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="Atualizado em"),
                ),
                (
                    "empresa",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="categorias",
                        to="tenants.empresa",
                        verbose_name="Empresa",
                    ),
                ),
            ],
            options={
                "verbose_name": "Categoria",
                "verbose_name_plural": "Categorias",
                "ordering": ["ordem", "nome"],
            },
        ),
        migrations.AddConstraint(
            model_name="categoria",
            constraint=models.UniqueConstraint(
                fields=("empresa", "slug"), name="unique_categoria_empresa_slug"
            ),
        ),
    ]
