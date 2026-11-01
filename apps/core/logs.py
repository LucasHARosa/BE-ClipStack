"""Logging estruturado em JSON (uma linha por evento), pronto para Loki/ELK/CloudWatch.

Configurado em settings.LOGGING. Todo registro ganha request_id e user_id da requisição atual
(contextvars), sem que quem loga precise passá-los.
"""

import json
import logging
from datetime import UTC, datetime

from apps.core.request_context import request_id_var, user_id_var

# Atributos que todo LogRecord tem; o resto veio do extra={...} de quem logou.
_STANDARD_ATTRS = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}


class RequestContextFilter(logging.Filter):
    def filter(self, record):
        if getattr(record, "request_id", None) is None:
            record.request_id = request_id_var.get()
        if getattr(record, "user_id", None) is None:
            record.user_id = user_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        payload.update({k: v for k, v in record.__dict__.items() if k not in _STANDARD_ATTRS})
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)
