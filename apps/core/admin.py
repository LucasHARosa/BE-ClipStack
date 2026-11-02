from django.contrib import admin

from .models import IdempotencyKey


class ModerationAdminMixin:
    # Mesma regra da API: o ADMIN modera (vê e apaga), mas não edita conteúdo alheio.
    moderator_can_delete = False

    def _is_moderator(self, request):
        return request.user.is_active and getattr(request.user, "is_admin", False)

    def has_module_permission(self, request):
        return request.user.is_superuser or self._is_moderator(request)

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser or self._is_moderator(request)

    def has_add_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser or (
            self.moderator_can_delete and self._is_moderator(request)
        )

    def has_moderate_permission(self, request):
        return request.user.is_superuser or self._is_moderator(request)


# Sem o mixin: diagnóstico, só para o superuser.
@admin.register(IdempotencyKey)
class IdempotencyKeyAdmin(admin.ModelAdmin):
    list_display = ("key", "user", "request_path", "response_status", "created_at")
    search_fields = ("key", "user__email")
    list_select_related = ("user",)
    readonly_fields = ("user", "key", "request_path", "response_status", "response_snapshot")
