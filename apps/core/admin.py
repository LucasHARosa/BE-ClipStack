"""Regras de acesso ao Django Admin compartilhadas pelas apps."""

from django.contrib import admin

from .models import IdempotencyKey


class ModerationAdminMixin:
    # has_*_permission(): hooks do ModelAdmin que decidem o que cada usuário pode fazer.
    # Mesma regra da API: o ADMIN (moderação) vê tudo e apaga para moderação, mas NÃO edita
    # conteúdo de outras pessoas. Só o superuser (equipe técnica) pode tudo.
    # Sem isso, um staff sem permissões do auth não veria nada no Admin.
    moderator_can_delete = False

    def _is_moderator(self, request):
        # getattr: core não importa accounts; basta o user ter a property is_admin.
        return request.user.is_active and getattr(request.user, "is_admin", False)

    def has_module_permission(self, request):
        return request.user.is_superuser or self._is_moderator(request)

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser or self._is_moderator(request)

    # obj=None deixa a mesma assinatura servir para ModelAdmin e para inlines.
    def has_add_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser or (
            self.moderator_can_delete and self._is_moderator(request)
        )


# Sem o mixin: só o superuser vê (staff sem permissões do auth não acessa). É ferramenta
# de diagnóstico, não de moderação.
@admin.register(IdempotencyKey)
class IdempotencyKeyAdmin(admin.ModelAdmin):
    list_display = ("key", "user", "request_path", "response_status", "created_at")
    search_fields = ("key", "user__email")
    list_select_related = ("user",)
    readonly_fields = ("user", "key", "request_path", "response_status", "response_snapshot")
