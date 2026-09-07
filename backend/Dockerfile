FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl fonts-dejavu-core libcairo2 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY . .

# Default container port. Railway / other PaaS overlays supply PORT at
# runtime; the entrypoint below falls back to 8000 when PORT is unset so
# local Docker / docker-compose behaviour is unchanged.
EXPOSE 8000

# Healthcheck uses the runtime PORT so it probes the SAME effective port
# the app is listening on. Wrapped in ``sh -c`` so the ${PORT:-8000}
# expansion happens at container start, not at image build time.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD sh -c "curl --fail --silent http://localhost:${PORT:-8000}/api/ || exit 1"

# Shell-form CMD so Railway's PORT is honored at runtime. Local
# ``docker run`` / docker-compose without PORT still bind to 8000.
CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT:-8000}"]
