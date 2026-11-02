from apps.accounts.exceptions import CannotChangeOwnRole


def set_user_role(*, user, role, actor):
    # Evita o admin se trancar fora (e o sistema ficar sem nenhum admin).
    if user.pk == actor.pk:
        raise CannotChangeOwnRole()
    user.role = role
    # save() para sincronizar o is_staff, que também precisa estar no update_fields.
    user.save(update_fields=["role", "is_staff"])
    return user
