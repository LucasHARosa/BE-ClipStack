class DomainError(Exception):
    status_code = 400
    code = "domain_error"
    message = "A operação não pode ser realizada."

    def __init__(self, message=None, *, details=None):
        self.message = message or self.message
        self.details = details or {}
        super().__init__(self.message)


class ConflictError(DomainError):
    status_code = 409
    code = "conflict"


class IdempotencyKeyReused(DomainError):
    status_code = 422
    code = "idempotency_key_reused"
    message = "Esta Idempotency-Key já foi usada em outra operação."
