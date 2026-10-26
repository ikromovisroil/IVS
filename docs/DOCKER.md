# IVS — Docker bilan ishga tushirish

Bitta image (`Dockerfile`) ichida: Django (ASGI, `daphne`), Celery, Telegram bot va yangi React interfeysi (`/app/`).
`docker-compose.yml` servislari: `db` (Postgres 16), `redis`, `web`, `worker`, `beat`, `bot`, `nginx`.

## Birinchi ishga tushirish

```bash
cp .env.docker.example .env        # SECRET_KEY, POSTGRES_PASSWORD, SSO_*, TELEGRAM_BOT_TOKEN va boshqalarni to'ldiring
docker compose up -d --build
docker compose ps                  # hamma servis "healthy"/"running" bo'lishi kerak
docker compose logs -f web
```

- Sayt: `http://<server>/` (nginx, 80-port; `HTTP_PORT` bilan o'zgartiriladi) → yangi interfeys `/app/`.
- Migratsiyani `web` servisi o'zi bajaradi (`RUN_MIGRATIONS=1`).
- Admin foydalanuvchi: `docker compose exec web python manage.py createsuperuser`.

## HTTPS

Konteynerlar ichida TLS yo'q. Productionda `report.example.uz` oldida HTTPS tugatuvchi tashqi proksi turishi kerak
(server nginx'i, Caddy, Cloudflare, yuk balanslagich) va u konteyner nginx'iga `X-Forwarded-Proto: https` bilan yuborishi kerak.
Django `DEBUG=0` da HTTPS ni majburlaydi (`SECURE_SSL_REDIRECT`, secure cookie, HSTS).

Faqat HTTP orqali sinash uchun (masalan, `http://localhost`): `.env` ga `HTTPS_ONLY=0` va
`CSRF_TRUSTED_ORIGINS=http://localhost` qo'shing. **Productionda `HTTPS_ONLY=0` qo'ymang.**

## Ma'lumotlar (volume'lar)

| Volume | Nima |
|---|---|
| `pgdata` | Postgres ma'lumotlari |
| `redisdata` | Redis (Celery navbati, chat, kesh) |
| `media` | Yuklangan fayllar (hujjat PDF, rasm). `web` yozadi, `nginx` `/media/` ni beradi |
| `logs` | Django xato logi (`/app/logs/error.log`) |

Zaxira nusxa (Postgres):

```bash
docker compose exec db pg_dump -U ivs ivs > backup_$(date +%F).sql
```

## Yangilash

```bash
git pull
docker compose up -d --build       # image qayta quriladi (frontend ham), web migratsiyani bajaradi
```

## Maxfiy kalitlar

- **VAPID (brauzer push) maxfiy kaliti** image ichiga kirmaydi: `private_key.pem` konteynerga faqat o'qish uchun ulanadi
  (`VAPID_PRIVATE_KEY_FILE=/run/secrets/vapid_private.pem`). Boshqa joydan berish uchun `.env` da `VAPID_PRIVATE_KEY_PATH`.
  Kalit fayli bo'lmasa Docker o'rniga papka yaratadi va push ishlamaydi.
- **Firebase (Android FCM)** fayli: volume orqali ulab, `.env` da `FIREBASE_CREDENTIALS_FILE` yo'lini bering.
- `.env` git'ga tushmaydi va image'ga kirmaydi (`.dockerignore`).

## Muhim eslatmalar

- **Telegram bot faqat bitta nusxada ishlashi kerak.** `TELEGRAM_BOT_TOKEN` bo'lmasa `bot` servisini o'chiring
  (`docker compose up -d --scale bot=0`).
- `ALLOWED_HOSTS` ichida `localhost` bo'lishi kerak (`web` healthcheck shu host bilan so'raydi).
- Eski SQLite bazadan o'tish: `dumpdata`/`loaddata` yoki `pgloader` kerak bo'ladi (bu fayllar avtomatik ko'chirmaydi).
- SSO: `SSO_REDIRECT_URI` yangi domenga mos bo'lishi va SSO tomonida ro'yxatdan o'tgan bo'lishi kerak.
- PDF: `PDF_ENGINE=weasyprint` (Linux'da tayyor). Times New Roman o'rniga Liberation Serif shrifti ishlatiladi
  (o'lchamlari bir xil), shuning uchun PDF ko'rinishi Windows'dagidan biroz farq qilishi mumkin.

## Foydali buyruqlar

```bash
docker compose exec web python manage.py migrate
docker compose exec web python manage.py check
docker compose logs -f worker beat bot
docker compose restart web
docker compose down              # servislarni to'xtatish (volume'lar saqlanadi)
```
