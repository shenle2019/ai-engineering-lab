#!/usr/bin/env bash
# Restart the prod stack, prove the data survives, then take a pg_dump backup.
set -euo pipefail

ROOT=/mnt/e/ailearning/python-luffycity/.tmp_mealie_work
DST=/opt/mealie
LOG="$ROOT/logs/16_prod_restart_backup.log"
exec > >(tee -a "$LOG") 2>&1

echo "=== $(date '+%F %T') restart mealie ==="
cd "$DST"
docker compose --env-file .env.production -f docker-compose.prod.yml restart mealie

for i in $(seq 1 30); do
  status=$(docker inspect -f '{{.State.Health.Status}}' mealie_app 2>/dev/null || echo unknown)
  echo "wait $i: $status"
  [ "$status" = "healthy" ] && break
  sleep 5
done

echo "=== $(date '+%F %T') verify data survived restart ==="
set -a
# shellcheck disable=SC1091
. "$DST/.env.production"
set +a

docker exec mealie_postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -tAc "select slug, difficulty from recipes order by created_at;"

echo "--- recipe readable through nginx ---"
curl -s -o /dev/null -w 'about=%{http_code}\n' http://127.0.0.1:8080/api/app/about

echo "=== $(date '+%F %T') pg_dump backup ==="
BACKUP="$DST/backups/mealie_$(date +%Y%m%d_%H%M%S).sql"
docker exec mealie_postgres pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" > "$BACKUP"
ls -lh "$BACKUP"
echo "--- backup head ---"
head -5 "$BACKUP"
echo "--- backup tail ---"
tail -3 "$BACKUP"

echo "=== $(date '+%F %T') done ==="
