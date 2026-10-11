import django.db.models.deletion
from django.db import migrations, models
from django.utils.text import slugify

LABELS = {
    "CAMISA_SOCIAL": "Camisas Sociais",
    "ESTAMPADA": "Estampadas",
    "BASICA": "Básicas",
    "MOLETOM": "Moletons e Jaquetas",
    "CALCA": "Calças e Bermudas",
    "FITNESS": "Moda Fitness",
    "OUTROS": "Outros",
}
ORDEM = {valor: indice for indice, valor in enumerate(LABELS)}


def criar_categorias_a_partir_do_legado(apps, schema_editor):
    Modelo = apps.get_model("produtos", "Modelo")
    Categoria = apps.get_model("produtos", "Categoria")

    cache = {}
    for modelo in Modelo.objects.all().iterator():
        valor = (getattr(modelo, "categoria", "") or "BASICA").upper()
        if valor not in LABELS:
            valor = "OUTROS"

        chave = (modelo.empresa_id, valor)
        categoria = cache.get(chave)
        if categoria is None:
            nome = LABELS[valor]
            categoria, _ = Categoria.objects.get_or_create(
                empresa_id=modelo.empresa_id,
                slug=slugify(nome)[:90],
                defaults={"nome": nome, "ordem": ORDEM[valor]},
            )
            cache[chave] = categoria

        modelo.categoria_fk_id = categoria.pk
        modelo.save(update_fields=["categoria_fk"])


class Migration(migrations.Migration):

    dependencies = [
        ("produtos", "0004_categoria"),
    ]

    operations = [
        migrations.AddField(
            model_name="modelo",
            name="categoria_fk",
            field=models.ForeignKey(
                blank=True,
                help_text="Utilizada no menu de navegação do catálogo público.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="produtos",
                to="produtos.categoria",
                verbose_name="Categoria",
            ),
        ),
        migrations.RunPython(
            criar_categorias_a_partir_do_legado,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.RemoveField(
            model_name="modelo",
            name="categoria",
        ),
        migrations.RenameField(
            model_name="modelo",
            old_name="categoria_fk",
            new_name="categoria",
        ),
    ]
