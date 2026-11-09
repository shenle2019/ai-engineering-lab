#!/usr/bin/env bash
# 一键复跑全部阶段，日志写入 ../logs/
# 用法：在本机 WSL 里执行 bash scripts/run_all.sh
set -uo pipefail

DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
LOG="$DIR/../logs"
mkdir -p "$LOG"

stages=(00_linux_basics 01_single_container 02_dockerfile 03_compose 04_migrate)

for s in "${stages[@]}"; do
  echo ">>> running $s"
  bash "$DIR/$s.sh" > "$LOG/$s.log" 2>&1
  rc=$?
  echo "    exit=$rc  log=logs/$s.log"
  if [ $rc -ne 0 ]; then
    echo "    !! 阶段失败，后续阶段仍继续（各阶段脚本内部用 -u 而非 -e）"
  fi
done

echo
echo "all stages done. logs: $LOG"
