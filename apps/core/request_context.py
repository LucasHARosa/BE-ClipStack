"""Dados da requisição atual disponíveis para qualquer log, sem passar `request` adiante.

contextvars: cada thread (worker sync) ou task asyncio tem o próprio valor. É o equivalente ao
AsyncLocalStorage do Node.
"""

from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_var: ContextVar[int | None] = ContextVar("user_id", default=None)
