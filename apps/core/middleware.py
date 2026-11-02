import logging
import re
import time
import uuid

from apps.core.request_context import request_id_var, user_id_var

logger = logging.getLogger("clipstack.request")

# Só reaproveita o id de quem chamou se for seguro para log e header.
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def _describe_user(user):
    if user is None:
        return None
    return "anonymous" if not user.is_authenticated else f"user:{user.pk}"


class RequestIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = request.headers.get("X-Request-ID", "")
        request_id = incoming if _VALID_REQUEST_ID.match(incoming) else uuid.uuid4().hex
        request.request_id = request_id
        request_token = request_id_var.set(request_id)
        user_token = user_id_var.set(None)

        # Com JWT, aqui ainda é AnonymousUser: o DRF só autentica dentro da view.
        user_before_view = _describe_user(getattr(request, "user", None))
        started = time.perf_counter()
        try:
            response = self.get_response(request)
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 1)
            request_id_var.reset(request_token)

        logger.info(
            "request_finished",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
                "user_before_view": user_before_view,
                "user_after_view": _describe_user(getattr(request, "user", None)),
                "user_id": user_id_var.get(),
            },
        )
        user_id_var.reset(user_token)
        response["X-Request-ID"] = request_id
        return response
