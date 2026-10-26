# syntax=docker/dockerfile:1
# IVS: Django (ASGI/daphne) + Celery + Telegram bot + yangi React interfeysi (/app/) — bitta image, har xil buyruq bilan.

# ─── 1) Frontend (React/Vite) build: natija /build/static/spa (vite.config.ts: outDir ../static/spa) ───
FROM node:22-alpine AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ─── 2) Ilova ───
FROM python:3.12-slim-bookworm AS app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# WeasyPrint (hujjat PDF) uchun tizim kutubxonalari va shriftlar (Times New Roman o'rniga Liberation Serif)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libffi8 libjpeg62-turbo libopenjp2-7 \
        shared-mime-info fonts-liberation fonts-dejavu-core tini \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# req.txt — UTF-16 (Windows); pip uchun UTF-8 ga o'giriladi
COPY req.txt /tmp/req.txt
RUN python -c "open('/tmp/requirements.txt','w',encoding='utf-8').write(open('/tmp/req.txt','rb').read().decode('utf-16'))" \
    && pip install -r /tmp/requirements.txt \
    && rm /tmp/req.txt /tmp/requirements.txt

COPY . .
COPY --from=frontend /build/static/spa ./static/spa

# Static fayllarni yig'ish (WhiteNoise beradi). Build vaqtida faqat SECRET_KEY kerak (ma'lumotlar bazasiga ulanilmaydi).
RUN SECRET_KEY=build-only DEBUG=0 python manage.py collectstatic --noinput

# Oddiy foydalanuvchi; media va logs — volume'lar uchun. entrypoint.sh: CRLF bo'lsa LF ga o'giriladi.
RUN useradd --system --create-home --uid 1000 app \
    && mkdir -p /app/media /app/logs /app/staticfiles \
    && chown -R app:app /app/media /app/logs /app/staticfiles \
    && sed -i 's/\r$//' /app/docker/entrypoint.sh \
    && chmod +x /app/docker/entrypoint.sh
USER app

EXPOSE 8000
ENTRYPOINT ["/usr/bin/tini", "--", "/app/docker/entrypoint.sh"]
CMD ["daphne", "--proxy-headers", "-b", "0.0.0.0", "-p", "8000", "config.asgi:application"]
