from apps.core.exceptions import ConflictError


class CannotChangeOwnRole(ConflictError):
    code = "cannot_change_own_role"
    message = "Você não pode alterar o seu próprio papel."
