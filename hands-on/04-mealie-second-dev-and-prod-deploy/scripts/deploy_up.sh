#!/usr/bin/env bash
# Bring up the production stack on /opt/mealie and verify it.
set -euo pipefail

ROOT=/mnt/e/ailearning/python-luffycity/.tmp_mealie_work
SRC="$ROOT/deploy"
DST=/opt/mealie
LOG="$ROOT/logs/13_deploy_up.log"

exec > >(tee -a "$LOG") 2>&1

echo "=== $(date '+%F %T') prepare $DST ==="
mkdir -p "$DST"/data/mealie "$DST"/postgres/data "$DST"/nginx/conf.d "$DST"/backups
cp "$SRC/docker-compose.prod.yml" "$DST/"
cp "$SRC/nginx/conf.d/mealie.conf" "$DST/nginx/conf.d/"
cp "$SRC/.env.production.example" "$DST/.env.production.example"

# Copy the real key from the dev env without echoing it into the log.
OPENAI_KEY=$(grep -E '^OPENAI_API_KEY=' "$ROOT/mealie/.env" | cut -d= -f2-)
if [ -z "$OPENAI_KEY" ]; then
  echo "!! OPENAI_API_KEY not found in mealie/.env"
  exit 1
fi

# Idempotent: keep the existing secrets once postgres has been initialized.
if [ ! -f "$DST/.env.production" ]; then
  cat > "$DST/.env.production" <<EOF
ALLOW_SIGNUP=false
PUID=1000
PGID=1000
TZ=Asia/Shanghai
BASE_URL=http://localhost:8080
DB_ENGINE=postgres
POSTGRES_USER=mealie
POSTGRES_PASSWORD=mealie-prod-$(date +%s | tail -c 7)
POSTGRES_SERVER=postgres
POSTGRES_PORT=5432
POSTGRES_DB=mealie
API_PORT=9000
LOG_LEVEL=INFO
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_API_KEY=${OPENAI_KEY}
OPENAI_MODEL=deepseek-chat
OPENAI_REQUEST_TIMEOUT=120
EOF
  chmod 600 "$DST/.env.production"
  echo "created $DST/.env.production"
else
  echo "keeping existing $DST/.env.production (secrets must match the initialized database)"
fi

# Ensure the LLM key is present even when the file already existed.
if ! grep -q '^OPENAI_API_KEY=..*' "$DST/.env.production"; then
  echo "OPENAI_API_KEY=${OPENAI_KEY}" >> "$DST/.env.production"
fi

echo "=== $(date '+%F %T') docker compose up -d ==="
cd "$DST"
docker compose --env-file .env.production -f docker-compose.prod.yml up -d
sleep 5
docker compose --env-file .env.production -f docker-compose.prod.yml ps
echo "=== $(date '+%F %T') done ==="
