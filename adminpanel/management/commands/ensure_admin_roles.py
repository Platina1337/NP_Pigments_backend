from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand


REQUIRED_GROUPS = ["admin", "content_manager", "orders_manager"]


class Command(BaseCommand):
    help = "Создает группы для кастомной админки, если их еще нет."

    def handle(self, *args, **options):
        created = []
        for name in REQUIRED_GROUPS:
            group, was_created = Group.objects.get_or_create(name=name)
            if was_created:
                created.append(name)

        if created:
            self.stdout.write(self.style.SUCCESS(f"Созданы группы: {', '.join(created)}"))
        else:
            self.stdout.write("Группы уже существуют, изменений нет.")

