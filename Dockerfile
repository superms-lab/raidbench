FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    RAIDBENCH_MODE=production \
    RAIDBENCH_HOST=0.0.0.0 \
    RAIDBENCH_PORT=8080 \
    RAIDBENCH_DB_PATH=/data/raidbench.db

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 raidbench \
    && mkdir -p /data \
    && chown raidbench:raidbench /data

COPY --chown=raidbench:raidbench . /app

USER raidbench
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=3)" || exit 1

CMD ["python", "backend/server.py"]
