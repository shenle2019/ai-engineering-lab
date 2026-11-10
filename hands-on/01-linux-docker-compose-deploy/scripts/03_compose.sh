#!/usr/bin/env bash
# 阶段 03：Docker Compose 编排 web + redis + nginx（对应预习3 day06 的多容器编排）
# 验证点：yml 校验、一键构建启动、服务名通信、healthcheck 依赖、nginx 反代、卷持久化
set -uo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
SRC=$(dirname "$SCRIPT_DIR")
WORK=/opt/lab/stage03
rm -rf "$WORK" 2>/dev/null; mkdir -p "$WORK"

hr() { echo; echo "===== $* ====="; }

hr "0 清理历史编排"
docker compose -f "$SRC/compose/docker-compose.yml" down -v >/dev/null 2>&1
echo "clean done"

hr "1 拷贝上下文（app + compose）到项目目录"
cp -r "$SRC/app" "$WORK/app"
cp -r "$SRC/compose" "$WORK/compose"
cd "$WORK/compose"
find . -maxdepth 2 -type f | sort

hr "2 校验 compose 文件"
docker compose config --quiet && echo "compose config OK"

hr "3 一键构建并启动（--build）"
docker compose up -d --build 2>&1 | tail -8
sleep 8
docker compose ps

hr "4 经 nginx 反代访问三次，验证服务名通信与计数"
for i in 1 2 3; do
  echo "--- 第 $i 次（curl http://localhost:8088/  ->  nginx -> web -> redis）"
  curl -s http://localhost:8088/
done

hr "5 直接进容器验证内部链路"
echo "--- web 容器解析 redis 主机名"; docker compose exec -T web python -c "import socket; print('redis ->', socket.gethostbyname('redis'))"
echo "--- redis 里的计数"; docker compose exec -T redis redis-cli GET visits
echo "--- nginx 配置里的 upstream"; docker compose exec -T nginx sh -c 'grep proxy_pass /etc/nginx/conf.d/default.conf'

hr "6 依赖顺序：redis healthcheck 通过后 web 才启动"
docker inspect lab-compose-redis --format 'health={{.State.Health.Status}}'
docker compose ps --format '{{.Name}}\t{{.Status}}'

hr "7 重启编排（down 保留卷），验证计数未丢"
docker compose down >/dev/null 2>&1
docker compose up -d >/dev/null 2>&1
sleep 8
echo "--- 重启后计数"; curl -s http://localhost:8088/
echo "--- redis 卷内容"; docker compose exec -T redis redis-cli GET visits
echo "--- 卷存在性"; docker volume ls --format '{{.Name}}' | grep lab_compose_redis_data

hr "8 日志汇总"
docker compose logs --tail 4 --no-log-prefix web
docker compose logs --tail 2 --no-log-prefix nginx

hr "9 收尾：停止并清理（保留卷）"
docker compose down >/dev/null 2>&1
echo "stack removed, volume kept: $(docker volume ls -q | grep -c lab_compose_redis_data)"

hr "DONE stage03"
