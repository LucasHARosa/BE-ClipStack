"""Exceções do processamento.

Duas famílias com tratamento diferente na task (etapa 8):
- TransientProcessingError: falha temporária (timeout, ffmpeg indisponível) → retry com backoff.
- ProcessingError: falha permanente (arquivo corrompido) → marca failed sem retry.
"""

from apps.core.exceptions import ConflictError


class ProcessingError(Exception):
    pass


class TransientProcessingError(ProcessingError):
    pass


class ProcessingAlreadyActive(ConflictError):
    code = "processing_already_active"
    message = "Este vídeo já tem um processamento em andamento."
