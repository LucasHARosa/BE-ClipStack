"""Exceções de domínio da app videos."""

from apps.core.exceptions import ConflictError


class VideoNotReprocessable(ConflictError):
    code = "video_not_reprocessable"
    message = "Só é possível reprocessar vídeos cujo processamento falhou."
