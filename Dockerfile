# Multi-stage: o estágio "builder" tem o uv e instala as dependências; o "runtime" recebe só
# o ambiente pronto (.venv + código). A imagem final fica menor e sem ferramentas de build.

# ---------------------------------------------------------------- builder
FROM python:3.14-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# Primeiro só os arquivos de dependência: enquanto eles não mudam, o Docker reaproveita esta
# camada (cache) e não reinstala tudo a cada mudança no código.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY . .
RUN uv sync --frozen --no-dev

# ---------------------------------------------------------------- runtime
FROM python:3.14-slim AS runtime
# ffmpeg/ffprobe para o FfmpegVideoProcessor.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
# Usuário sem privilégios: se a aplicação for comprometida, o atacante não é root no container.
RUN useradd --create-home --uid 1000 app \
    && mkdir -p /app/media /app/staticfiles \
    && chown -R app:app /app
WORKDIR /app
COPY --from=builder --chown=app:app /app /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.prod \
    MEDIA_ROOT=/app/media
USER app
