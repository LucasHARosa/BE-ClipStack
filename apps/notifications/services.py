"""Casos de uso que ESCREVEM (regra de negócio, transações, enfileiramento de tasks).

Funções com argumentos nomeados; views e tasks chamam essas funções em vez de mexer nos
models diretamente.
"""

from apps.notifications.models import Notification


def mark_all_read(*, user):
    # QuerySet.update(): um único UPDATE no banco, sem carregar os objetos. Ok aqui porque
    # Notification não tem lógica no save() nem signals. Devolve o número de linhas.
    return Notification.objects.filter(user=user, is_read=False).update(is_read=True)
