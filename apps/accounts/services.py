"""Casos de uso que ESCREVEM (regra de negócio, transações, enfileiramento de tasks).

Funções com argumentos nomeados (ex.: set_user_role(*, user, role)); views e tasks chamam
essas funções em vez de mexer nos models diretamente.
"""


def set_user_role(*, user, role):
    user.role = role
    # save() (e não QuerySet.update()) para o User.save() sincronizar o is_staff.
    # update_fields precisa listar is_staff também: senão o save() calcula o valor novo,
    # mas o UPDATE grava só o role.
    user.save(update_fields=["role", "is_staff"])
    return user
