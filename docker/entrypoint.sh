#!/bin/sh
# Konteyner ishga tushishi: (ixtiyoriy) bazani kutish, migratsiya, keyin asosiy buyruq.
set -e

# Ma'lumotlar bazasi tayyor bo'lguncha kutish (Postgres ishlatilganda)
if [ "${USE_POSTGRES:-0}" = "1" ] && [ "${WAIT_FOR_DB:-1}" = "1" ]; then
python - <<'PY'
import os, socket, sys, time

host = os.environ.get("DB_HOST", "db")
port = int(os.environ.get("DB_PORT", "5432"))
for attempt in range(60):
    try:
        socket.create_connection((host, port), timeout=2).close()
        break
    except OSError:
        time.sleep(1)
else:
    sys.exit(f"Ma'lumotlar bazasi javob bermadi: {host}:{port}")
PY
fi

# Migratsiyani faqat bitta konteyner (web) bajaradi: RUN_MIGRATIONS=1
if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
    python manage.py migrate --noinput
fi

exec "$@"
