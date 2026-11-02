"""Health check: GET /api/v1/health/ → 200 se banco, Redis e RabbitMQ respondem; senão 503.

View ASYNC nativa do Django (async def), não do DRF: o DRF não suporta views async (APIView,
autenticação e permissões são síncronas). Por isso ela não passa por JWT, throttling nem pelo
exception handler da API, e é pública (o orquestrador, como Docker ou k8s, chama sem token).

Por que async aqui: são 3 esperas de I/O independentes. Com asyncio.gather elas rodam ao mesmo
tempo, e o tempo total ≈ a mais lenta, não a soma.
- Sob ASGI (Uvicorn), a view roda no event loop do servidor, sem ocupar uma thread.
- Sob WSGI (Gunicorn sync, runserver), o Django cria um event loop por requisição
  (async_to_sync). O paralelismo DENTRO da requisição continua valendo, mas o worker fica
  ocupado do mesmo jeito. Async só ganha escala de verdade sob ASGI.
"""

import asyncio
import time

import redis.asyncio as aioredis
from asgiref.sync import sync_to_async
from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from kombu import Connection

CHECK_TIMEOUT_SECONDS = 2.0


def _check_database():
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    finally:
        # Cada thread do executor abre a própria conexão; fecha para não vazar.
        connection.close()


async def _check_redis():
    client = aioredis.from_url(settings.CACHES["default"]["LOCATION"])
    try:
        await client.ping()  # cliente async de verdade: não ocupa thread
    finally:
        await client.aclose()


def _check_rabbitmq():
    # kombu é síncrono: roda numa thread (sync_to_async) para não travar o event loop.
    with Connection(settings.CELERY_BROKER_URL, connect_timeout=CHECK_TIMEOUT_SECONDS) as conn:
        conn.ensure_connection(max_retries=1)


async def _timed(name, coroutine):
    started = time.perf_counter()
    try:
        await asyncio.wait_for(coroutine, timeout=CHECK_TIMEOUT_SECONDS)
        ok, error = True, None
    except Exception as exc:  # noqa: BLE001 (qualquer falha = dependência indisponível)
        ok, error = False, f"{type(exc).__name__}: {exc}"[:200]
    result = {"ok": ok, "latency_ms": round((time.perf_counter() - started) * 1000, 1)}
    if error:
        result["error"] = error
    return name, result


async def health_view(request):
    started = time.perf_counter()
    # thread_sensitive=False: cada check síncrono roda numa thread própria, em paralelo.
    # (O padrão, True, usaria uma única thread compartilhada e os checks ficariam em fila.)
    results = await asyncio.gather(
        _timed("database", sync_to_async(_check_database, thread_sensitive=False)()),
        _timed("redis", _check_redis()),
        _timed("rabbitmq", sync_to_async(_check_rabbitmq, thread_sensitive=False)()),
    )
    checks = dict(results)
    healthy = all(check["ok"] for check in checks.values())
    body = {
        "status": "ok" if healthy else "degraded",
        "checks": checks,
        "total_ms": round((time.perf_counter() - started) * 1000, 1),
    }
    # 503: o load balancer/orquestrador tira a instância de rotação enquanto algo estiver fora.
    return JsonResponse(body, status=200 if healthy else 503)
