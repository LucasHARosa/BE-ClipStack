"""Permissões customizadas do DRF.

Divisão de trabalho (o que gera 404 e o que gera 403):
- get_queryset() decide o que o usuário PODE VER. Fora dele, get_object() → 404, sem revelar
  que o recurso existe.
- As permissões de objeto daqui decidem o que ele pode FAZER com o que vê → 403.

Todas leem request.user (carregado do BANCO pela JWTAuthentication a cada requisição), NUNCA
o claim "role" do token: o claim pode estar desatualizado (usuário rebaixado depois do login)
e existe só para o frontend decidir o que mostrar.
"""

from rest_framework import permissions


def _is_admin(user):
    # Duck typing: core não importa accounts; basta o user ter a property is_admin.
    return bool(user and user.is_authenticated and getattr(user, "is_admin", False))


class HasRole(permissions.BasePermission):
    # has_permission(): roda em TODA requisição, antes do handler (nível de view).
    allowed_roles: tuple[str, ...] = ()

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role in self.allowed_roles)


class IsAdminRole(HasRole):
    allowed_roles = ("ADMIN",)


class IsOwnerOrReadOnly(permissions.BasePermission):
    # has_object_permission(): só roda quando a view chama get_object() (retrieve, update,
    # destroy, @action(detail=True)). NÃO roda no list: sozinha, não protege a listagem
    # (laboratório 1). Por isso a visibilidade fica no get_queryset().
    owner_field = "owner"

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        # Compara pelo _id para não disparar uma query extra só para carregar o dono.
        return getattr(obj, f"{self.owner_field}_id") == request.user.id


class IsAuthorOrAdmin(permissions.BasePermission):
    # Apagar comentário: o autor apaga o seu; o admin apaga qualquer um (moderação).
    message = "Só o autor ou um administrador pode apagar este comentário."

    def has_object_permission(self, request, view, obj):
        return obj.author_id == request.user.id or _is_admin(request.user)
