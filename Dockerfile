# ---------- Stage 1: run unit tests (pipeline runs: docker build --target test) ----------
FROM python:3.12-slim AS test
WORKDIR /src
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY app ./app
# app/ includes templates/ (HTML) and static/ (CSS)
COPY tests ./tests
RUN python -m pytest -v tests

# ---------- Stage 2: small production image ----------
FROM python:3.12-slim AS runtime
ARG APP_VERSION=dev
ENV APP_VERSION=${APP_VERSION} \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
# app/ includes templates/ (HTML) and static/ (CSS)
# Run as a non-root user (security best practice)
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin appuser
USER 10001
EXPOSE 5000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health')"
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--worker-tmp-dir", "/tmp", "app.main:app"]
