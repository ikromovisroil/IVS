#!/usr/bin/env bash
# IVS: serverda xavfsiz yangilash — zaxira → yangi kod → qurish → ishga tushirish → tekshirish.
# Ishga tushirish (loyiha papkasida):  bash docker/update.sh
# Muammo bo'lsa:                        bash docker/rollback.sh
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
BACKUPS="${IVS_BACKUPS:-$HOME/ivs-backups}"
mkdir -p "$BACKUPS"
STAMP="$(date +%F_%H%M)"
PORT="$(grep -E '^HTTP_PORT=' .env 2>/dev/null | tail -1 | cut -d= -f2 | tr -d "'\" " || true)"
PORT="${PORT:-8080}"

echo "1/6  Baza zaxirasi -> $BACKUPS/ivs_$STAMP.dump"
docker compose exec -T db pg_dump -U "${POSTGRES_USER:-ivs}" -Fc "${POSTGRES_DB:-ivs}" > "$BACKUPS/ivs_$STAMP.dump" < /dev/null
test -s "$BACKUPS/ivs_$STAMP.dump" || { echo "XATO: zaxira bo'sh, to'xtadim."; exit 1; }
# Disk to'lib ketmasligi uchun faqat oxirgi KEEP ta zaxira qoladi (rollback uchun oxirgisi yetarli)
KEEP="${IVS_KEEP_BACKUPS:-7}"
ls -1t "$BACKUPS"/ivs_*.dump 2>/dev/null | tail -n +"$((KEEP + 1))" | while read -r old; do rm -f -- "$old"; done || true

echo "2/6  Qaytish nuqtasi (hozirgi kod va tasvir)"
git rev-parse HEAD > "$BACKUPS/last_commit"
echo "$STAMP" > "$BACKUPS/last_backup"
docker tag ivs:latest ivs:prev 2>/dev/null || true

echo "3/6  Yangi kodni olish"
git pull --ff-only origin "$(git rev-parse --abbrev-ref HEAD)"

echo "4/6  Tasvirni qurish (sayt shu paytda ishlashda davom etadi)"
docker compose build < /dev/null

echo "5/6  Ishga tushirish (o'zgargan xizmatlar qayta yaratiladi, web migratsiyani o'zi bajaradi)"
docker compose up -d < /dev/null

echo "6/6  Tekshirish (portda javob kutilmoqda: $PORT)"
for i in $(seq 1 30); do
  if curl -fsS -o /dev/null -H "Host: localhost" -H "X-Forwarded-Proto: https" "http://127.0.0.1:$PORT/api/v1/spa/auth/config/"; then
    echo "OK: sayt javob beryapti."
    docker compose ps
    echo "Zaxira: $BACKUPS/ivs_$STAMP.dump  |  Qaytish kerak bo'lsa: bash docker/rollback.sh"
    exit 0
  fi
  sleep 3
done
echo "OGOHLANTIRISH: 90 soniyada javob olinmadi. Loglar: docker compose logs --tail=60 web"
echo "Qaytish: bash docker/rollback.sh"
exit 1
