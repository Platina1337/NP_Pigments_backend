from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AdminActionLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(max_length=128, verbose_name="Действие")),
                ("object_repr", models.CharField(blank=True, max_length=255, verbose_name="Объект")),
                ("object_id", models.CharField(blank=True, max_length=64, verbose_name="ID объекта")),
                ("extra", models.JSONField(blank=True, default=dict, verbose_name="Доп. данные")),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True, verbose_name="IP")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создано")),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.SET_NULL,
                        related_name="admin_actions",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Пользователь",
                    ),
                ),
            ],
            options={
                "verbose_name": "Действие админки",
                "verbose_name_plural": "Действия админки",
                "ordering": ["-created_at"],
            },
        ),
    ]

