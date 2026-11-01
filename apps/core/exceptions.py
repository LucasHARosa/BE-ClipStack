"""Exceções de domínio.

O service lança um erro de NEGÓCIO sem saber nada de HTTP (não recebe request nem devolve
Response). Quem traduz para status code e JSON é o exception handler da API
(apps/core/exception_handler.py). Assim o mesmo service serve à view, à task e ao Admin.
"""


class DomainError(Exception):
    # Valores padrão; cada subclasse define os seus.
    status_code = 400
    code = "domain_error"
    message = "A operação não pode ser realizada."

    def __init__(self, message=None, *, details=None):
        self.message = message or self.message
        self.details = details or {}
        super().__init__(self.message)


class ConflictError(DomainError):
    # 409 Conflict: o pedido é válido, mas conflita com o ESTADO atual do recurso.
    status_code = 409
    code = "conflict"


class IdempotencyKeyReused(DomainError):
    # 422: a mesma Idempotency-Key foi usada em outro endpoint, ou seja, outra operação.
    status_code = 422
    code = "idempotency_key_reused"
    message = "Esta Idempotency-Key já foi usada em outra operação."
