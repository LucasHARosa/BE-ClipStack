from django.contrib import admin

from .models import Notification


# Sem o ModerationAdminMixin de propósito: notificação é privada, nem o ADMIN vê as dos
# outros. Só o superuser (equipe técnica) acessa, para suporte e diagnóstico.
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "message", "video", "is_read", "created_at")
    list_filter = ("is_read",)
    search_fields = ("user__email", "message")
    list_select_related = ("user", "video")
