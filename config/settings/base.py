"""Settings comuns a todos os ambientes.

Configuração que muda entre ambientes (segredos, URLs de serviços) vem de variáveis de
ambiente (12-factor app), lidas com django-environ a partir do processo ou do arquivo .env.
"""

from datetime import timedelta
from pathlib import Path

import environ
from corsheaders.defaults import default_headers

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
# read_env não sobrescreve variáveis que já existem no processo (ex.: as do Docker/CI).
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])

# ---------------------------------------------------------------- apps
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]
THIRD_PARTY_APPS = [
    "corsheaders",
    "django_filters",
    "rest_framework",
    # Tabelas OutstandingToken/BlacklistedToken: logout e rotação de refresh tokens.
    "rest_framework_simplejwt.token_blacklist",
]
# Apps do projeto: uma por domínio (bounded context), não uma por camada.
LOCAL_APPS = [
    "apps.core",
    "apps.accounts",
    "apps.videos",
    "apps.processing",
    "apps.notifications",
]
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ---------------------------------------------------------------- middleware
# A ordem importa: na ida a requisição passa de cima para baixo; na volta, de baixo para cima.
# Detalhado em docs/00-antes-da-view.md (etapa 7 adiciona CORS e RequestId).
MIDDLEWARE = [
    # O mais alto possível: responde o preflight OPTIONS sem passar pelo resto e põe os
    # headers CORS também nas respostas geradas por outros middlewares (erros, redirects).
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Depois do AuthenticationMiddleware de propósito: assim ele consegue registrar o
    # request.user que um middleware enxerga (AnonymousUser com JWT, laboratório 2).
    "apps.core.middleware.RequestIdMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ---------------------------------------------------------------- banco
# env.db() converte DATABASE_URL (postgres://user:senha@host:porta/nome) no dict do Django.
DATABASES = {"default": env.db("DATABASE_URL")}
# Reaproveita a conexão por até 60s entre requisições do mesmo worker (evita reconectar sempre).
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------- cache
# Redis (backend nativo do Django 4+). Compartilhado entre TODOS os processos: com vários
# workers do Gunicorn, um cache em memória local daria um contador de throttling por worker
# (o limite efetivo seria N vezes maior) e um cache de estatísticas diferente em cada um.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("REDIS_URL", default="redis://localhost:6379/0"),
        "KEY_PREFIX": "clipstack",
    }
}

# ---------------------------------------------------------------- autenticação
# User customizado definido desde o primeiro migrate: trocar AUTH_USER_MODEL depois que as
# tabelas existem exige refazer migrations e mexer em FKs na mão.
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------- i18n
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
# USE_TZ: datas gravadas em UTC no banco e convertidas só na exibição.
USE_TZ = True

# ---------------------------------------------------------------- arquivos
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# MEDIA: arquivos enviados pelos usuários (vídeos e thumbnails).
MEDIA_URL = "media/"
MEDIA_ROOT = env.path("MEDIA_ROOT", default=BASE_DIR / "media")

# ---------------------------------------------------------------- CORS
# CORS (Cross-Origin Resource Sharing) é regra do NAVEGADOR: o JS de outra origem só lê a
# resposta se o servidor permitir. Não protege a API (curl/Postman ignoram); quem protege é
# autenticação + permissão. Lista explícita de origens, nunca CORS_ALLOW_ALL_ORIGINS.
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=["http://localhost:5173"])
# Headers que o JS do frontend pode mandar além dos padrões (authorization, content-type...).
CORS_ALLOW_HEADERS = (*default_headers, "idempotency-key", "x-request-id")
# Headers da resposta que o JS pode LER (por padrão, só os "simples").
CORS_EXPOSE_HEADERS = ["X-Request-ID", "Idempotent-Replayed", "Retry-After"]

# ---------------------------------------------------------------- upload de vídeos
# Regras de formato do upload, validadas no serializer e expostas ao frontend em /meta/.
VIDEO_ALLOWED_EXTENSIONS = env.list(
    "VIDEO_ALLOWED_EXTENSIONS", default=[".mp4", ".mov", ".webm", ".mkv"]
)
VIDEO_MAX_UPLOAD_SIZE_MB = env.int("VIDEO_MAX_UPLOAD_SIZE_MB", default=200)
# Arquivos acima deste tamanho vão para um arquivo temporário em disco, não para a memória.
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

# ---------------------------------------------------------------- processamento de vídeos
# DI por configuração: a implementação do processador é escolhida aqui (import_string).
# Fake em dev/testes; apps.processing.processors.FfmpegVideoProcessor quando há ffmpeg.
VIDEO_PROCESSOR_CLASS = env(
    "VIDEO_PROCESSOR_CLASS", default="apps.processing.processors.FakeVideoProcessor"
)
FAKE_PROCESSOR_STEP_SECONDS = env.float("FAKE_PROCESSOR_STEP_SECONDS", default=1.0)
# Inversão de dependência entre apps: videos precisa INICIAR o processamento, mas não pode
# importar processing (fronteira do import-linter). Então videos chama "a função configurada
# aqui", e é o settings (composition root) que liga as duas apps.
VIDEO_PROCESSING_ENTRYPOINT = "apps.processing.services.start_processing"

# ---------------------------------------------------------------- DRF
# Configuração global do DRF; cada etapa acrescenta (auth, permissões, paginação, throttle...).
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    # JWT no header "Authorization: Bearer <access>". Por ser a PRIMEIRA classe, quem não
    # mandou credencial recebe 401 com "WWW-Authenticate: Bearer" (e não 403).
    # ContextJWTAuthentication = JWTAuthentication do simplejwt + user_id no contexto de log.
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.core.authentication.ContextJWTAuthentication",
    ],
    # Fechado por padrão: todo endpoint exige login, e quem é público declara AllowAny.
    # Esquecer a permissão numa view nova não a deixa aberta.
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.DefaultPagination",
    # Filtros (django-filter), busca (?search=) e ordenação (?ordering=). Cada view declara
    # o que aceita (filterset_class, search_fields, ordering_fields); sem isso, não fazem nada.
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    # Converte DomainError (lançada pelos services) em resposta HTTP.
    "EXCEPTION_HANDLER": "apps.core.exception_handler.api_exception_handler",
    # Throttling: contadores no cache (Redis). Anônimo por IP; logado por id do usuário.
    # O "user" comporta o polling do frontend (1 GET a cada 2 s = 30/min por vídeo aberto).
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": env("THROTTLE_ANON", default="30/minute"),
        "user": env("THROTTLE_USER", default="120/minute"),
        # Scopes (ScopedRateThrottle): limites próprios em endpoints sensíveis.
        "upload": env("THROTTLE_UPLOAD", default="10/hour"),
        "login": env("THROTTLE_LOGIN", default="5/minute"),
    },
}

# ---------------------------------------------------------------- Celery
# Broker = RabbitMQ (guarda e entrega as mensagens, com ack real). Result backend = Redis
# (estado/resultado das tasks, usado pelo Flower). São papéis diferentes.
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="amqp://clipstack:clipstack@localhost:5672//")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://localhost:6379/1")
CELERY_RESULT_EXPIRES = 60 * 60 * 24
CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = TIME_ZONE

# Duas filas: "processing" (vídeo: pesado, lento, CPU/ffmpeg) e "default" (notificações e
# emails: leve, rápido). Com uma fila só, 50 vídeos na frente atrasariam todos os emails.
# Cada fila tem o próprio worker, escalado de forma independente.
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_ROUTES = {"apps.processing.tasks.process_video": {"queue": "processing"}}

# Prefetch 1: o worker só pega a próxima mensagem quando termina a atual. Com tasks longas,
# o padrão (4 por processo) deixaria mensagens "presas" num worker ocupado enquanto outro
# está livre.
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
# Com acks_late: se o processo do worker morrer no meio (OOM, kill), a mensagem volta à fila.
CELERY_TASK_REJECT_ON_WORKER_LOST = True
# RabbitMQ 4 não aceita mais filas "transient non-exclusive", que o Celery usava por padrão
# no controle remoto (pidbox: inspect/ping, Flower) e nos eventos. Exclusivas (presas à
# conexão que as criou) continuam permitidas.
CELERY_CONTROL_QUEUE_EXCLUSIVE = True
CELERY_EVENT_QUEUE_EXCLUSIVE = True
# Se a conexão com o broker cair, cancela as tasks em execução com acks_late: elas não podem
# mais ser confirmadas e o RabbitMQ já as devolveu à fila (padrão do Celery 6).
CELERY_WORKER_CANCEL_LONG_RUNNING_TASKS_ON_CONNECTION_LOSS = True
# Rede de segurança contra task travada: soft (exceção dentro da task) e hard (mata o processo).
CELERY_TASK_SOFT_TIME_LIMIT = 10 * 60
CELERY_TASK_TIME_LIMIT = 11 * 60

# Celery Beat: agenda tarefas periódicas (publica a mensagem; quem executa é um worker).
# Rodar UMA instância do beat; duas publicariam tudo em dobro.
CELERY_BEAT_SCHEDULE = {
    "fail-stuck-processing-jobs": {
        "task": "apps.processing.tasks.fail_stuck_jobs",
        "schedule": 5 * 60,  # a cada 5 minutos
    },
    "purge-old-idempotency-keys": {
        "task": "apps.core.tasks.purge_idempotency_keys",
        "schedule": 60 * 60,  # a cada hora
    },
}
# Job em "processing" há mais que isso (worker morreu, mensagem perdida) vira failed.
STUCK_JOB_TIMEOUT_MINUTES = env.int("STUCK_JOB_TIMEOUT_MINUTES", default=15)
IDEMPOTENCY_KEY_TTL_HOURS = 24

# ---------------------------------------------------------------- email
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="ClipStack <no-reply@clipstack.local>")

# ---------------------------------------------------------------- logging
# JSON no console (stdout): em container, quem coleta os logs é a plataforma (Docker, k8s),
# não arquivos. Cada linha leva request_id e user_id (RequestContextFilter).
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"request_context": {"()": "apps.core.logs.RequestContextFilter"}},
    "formatters": {"json": {"()": "apps.core.logs.JsonFormatter"}},
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "filters": ["request_context"],
        }
    },
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")},
    "loggers": {
        # O RequestIdMiddleware já registra cada requisição; evita a linha duplicada do Django.
        "django.request": {"level": "ERROR"},
        "django.server": {"level": "WARNING"},
    },
}

# ---------------------------------------------------------------- JWT (simplejwt)
SIMPLE_JWT = {
    # Access curto: vai em toda requisição; se vazar, expira logo. Não dá para revogar.
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env.int("JWT_ACCESS_MINUTES", default=15)),
    # Refresh longo: só serve para pedir novos access; pode ser revogado (blacklist).
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env.int("JWT_REFRESH_DAYS", default=7)),
    # Rotação: cada /refresh/ devolve um refresh NOVO e põe o antigo na blacklist. Um refresh
    # roubado para de funcionar assim que o dono legítimo usa o dele.
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}
