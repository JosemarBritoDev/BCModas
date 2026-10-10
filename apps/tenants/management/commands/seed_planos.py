from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.tenants.models import Plano

PLANOS = [
    {"nome": "Starter", "preco_mensal": Decimal("97.00"), "limite_usuarios": 1, "limite_produtos": 50},
    {"nome": "Pro", "preco_mensal": Decimal("197.00"), "limite_usuarios": 5, "limite_produtos": 300},
    {"nome": "Enterprise", "preco_mensal": Decimal("497.00"), "limite_usuarios": 999, "limite_produtos": 99999},
]


class Command(BaseCommand):
    help = "Cria/atualiza os 3 planos padrão do SaaS BC Modas (idempotente)."

    def handle(self, *args, **options):
        created = 0
        updated = 0
        for dados in PLANOS:
            plano, foi_criado = Plano.objects.update_or_create(
                nome=dados["nome"],
                defaults={
                    "preco_mensal": dados["preco_mensal"],
                    "limite_usuarios": dados["limite_usuarios"],
                    "limite_produtos": dados["limite_produtos"],
                },
            )
            if foi_criado:
                created += 1
                self.stdout.write(self.style.SUCCESS(f"Plano criado: {plano.nome}"))
            else:
                updated += 1
                self.stdout.write(f"Plano atualizado: {plano.nome}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed concluído: {created} criado(s), {updated} atualizado(s)."
            )
        )