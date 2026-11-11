#!/usr/bin/env bash
# Inspect the production postgres volume: migration head + the difficulty column.
set -euo pipefail

LOG=/mnt/e/ailearning/python-luffycity/.tmp_mealie_work/logs/14_prod_db_check.log
exec > >(tee -a "$LOG") 2>&1

echo "=== $(date '+%F %T') prod db check ==="
set -a
# shellcheck disable=SC1091
. /opt/mealie/.env.production
set +a

echo "--- alembic_version ---"
docker exec mealie_postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -tAc "select version_num from alembic_version;"

echo "--- recipes.difficulty ---"
docker exec mealie_postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -tAc "select column_name, data_type, is_nullable from information_schema.columns
        where table_name='recipes' and column_name='difficulty';"

echo "--- users ---"
docker exec mealie_postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -tAc "select username, email, admin from users;"

echo "--- recipes ---"
docker exec mealie_postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -tAc "select slug, name, difficulty from recipes;"

echo "=== $(date '+%F %T') done ==="
