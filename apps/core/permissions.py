"""Leem o papel de request.user (banco), nunca o claim do token, que pode estar velho."""

from rest_framework import permissions


def _is_admin(user):
    # getattr: core não importa accounts.
    return bool(user and user.is_authenticated and getattr(user, "is_admin", False))


class HasRole(permissions.BasePermission):
    allowed_roles: tuple[str, ...] = ()

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role in self.allowed_roles)


class IsAdminRole(HasRole):
    allowed_roles = ("ADMIN",)


class IsOwnerOrReadOnly(permissions.BasePermission):
    # Não roda no list: a visibilidade fica no get_queryset().
    owner_field = "owner"

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return getattr(obj, f"{self.owner_field}_id") == request.user.id


class IsAuthorOrAdmin(permissions.BasePermission):
    message = "Só o autor ou um administrador pode apagar este comentário."

    def has_object_permission(self, request, view, obj):
        return obj.author_id == request.user.id or _is_admin(request.user)
