from django.conf import settings
from django.db import models


class AdminActionLog(models.Model):
    """Базовый аудит действий в кастомной админке."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admin_actions",
        verbose_name="Пользователь",
    )
    action = models.CharField(max_length=128, verbose_name="Действие")
    object_repr = models.CharField(max_length=255, blank=True, verbose_name="Объект")
    object_id = models.CharField(max_length=64, blank=True, verbose_name="ID объекта")
    extra = models.JSONField(default=dict, blank=True, verbose_name="Доп. данные")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")

    class Meta:
        verbose_name = "Действие админки"
        verbose_name_plural = "Действия админки"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} ({self.object_repr or '—'})"

