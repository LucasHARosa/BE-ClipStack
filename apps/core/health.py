"""View async do Django (o DRF não suporta async): os 3 checks rodam em paralelo."""

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
        # Cada thread do executor abre a própria conexão.
        connection.close()


async def _check_redis():
    client = aioredis.from_url(settings.CACHES["default"]["LOCATION"])
    try:
        await client.ping()
    finally:
        await client.aclose()


def _check_rabbitmq():
    with Connection(settings.CELERY_BROKER_URL, connect_timeout=CHECK_TIMEOUT_SECONDS) as conn:
        conn.ensure_connection(max_retries=1)


async def _run_timed_check(name, coroutine):
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
    # thread_sensitive=False: com o padrão, os checks síncronos dividiriam uma thread só.
    results = await asyncio.gather(
        _run_timed_check("database", sync_to_async(_check_database, thread_sensitive=False)()),
        _run_timed_check("redis", _check_redis()),
        _run_timed_check("rabbitmq", sync_to_async(_check_rabbitmq, thread_sensitive=False)()),
    )
    checks = dict(results)
    healthy = all(check["ok"] for check in checks.values())
    body = {
        "status": "ok" if healthy else "degraded",
        "checks": checks,
        "total_ms": round((time.perf_counter() - started) * 1000, 1),
    }
    return JsonResponse(body, status=200 if healthy else 503)
