from apps.core.exceptions import ConflictError


class ProcessingError(Exception):
    pass


class TransientProcessingError(ProcessingError):
    pass


class ProcessingAlreadyActive(ConflictError):
    code = "processing_already_active"
    message = "Este vídeo já tem um processamento em andamento."
