#!/usr/bin/env bash
# IVS: oxirgi update.sh dan oldingi holatga qaytish (kod va tasvir). Ma'lumotlar bazasi o'zgarmaydi.
# Migratsiya sxemani o'zgartirgan bo'lsa, bazani zaxiradan tiklash kerak (oxirida buyruq chiqadi).
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
BACKUPS="${IVS_BACKUPS:-$HOME/ivs-backups}"
test -s "$BACKUPS/last_commit" || { echo "Qaytish nuqtasi topilmadi ($BACKUPS/last_commit)."; exit 1; }
PREV="$(cat "$BACKUPS/last_commit")"

echo "Kodni $PREV ga qaytarish"
git checkout "$PREV" < /dev/null
if docker image inspect ivs:prev > /dev/null 2>&1; then
  echo "Oldingi tasvir (ivs:prev) qayta tiklanmoqda"
  docker tag ivs:prev ivs:latest
  docker compose up -d --no-build < /dev/null
else
  echo "Oldingi tasvir yo'q, qayta quriladi"
  docker compose up -d --build < /dev/null
fi
docker compose ps
echo
echo "Kod endi 'detached HEAD' holatida. Keyin yangilash uchun:  git checkout xurshidui"
LAST="$(cat "$BACKUPS/last_backup" 2>/dev/null || true)"
if [ -n "$LAST" ]; then
  echo "Bazani ham qaytarish kerak bo'lsa (ma'lumotlar yangilanishdan keyingi holatda qolgan):"
  echo "  docker compose stop web worker beat bot"
  echo "  docker compose cp $BACKUPS/ivs_$LAST.dump db:/tmp/restore.dump"
  echo "  docker compose exec db pg_restore -U ivs -d ivs --no-owner --no-acl --clean --if-exists /tmp/restore.dump"
  echo "  docker compose up -d"
fi
