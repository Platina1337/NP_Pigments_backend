from django.contrib import admin

from .models import AdminActionLog


@admin.register(AdminActionLog)
class AdminActionLogAdmin(admin.ModelAdmin):
    list_display = ("action", "user", "object_repr", "object_id", "created_at", "ip_address")
    search_fields = ("action", "object_repr", "object_id", "user__username", "user__email")
    list_filter = ("action", "created_at")
    readonly_fields = ("user", "action", "object_repr", "object_id", "extra", "ip_address", "created_at")

