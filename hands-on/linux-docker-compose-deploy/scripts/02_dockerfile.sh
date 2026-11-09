#!/usr/bin/env bash
# 阶段 02：Dockerfile 构建 Flask 访问计数应用（对应预习2 day05 的 Dockerfile 与分层）
# 验证点：构建、镜像运行、自定义网络内服务通信、CMD/ENTRYPOINT、ARG/ENV、镜像分层
set -uo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
SRC=$(dirname "$SCRIPT_DIR")
WORK=/opt/lab/stage02
rm -rf "$WORK" 2>/dev/null; mkdir -p "$WORK/exp"; cd "$WORK"

hr() { echo; echo "===== $* ====="; }

hr "0 清理"
docker rm -f lab-web lab-cache >/dev/null 2>&1
docker network rm lab-net >/dev/null 2>&1
echo "clean done"

hr "1 拷贝上下文并构建镜像 lab-web:1.0"
cp -r "$SRC/app" "$WORK/app"
cd "$WORK/app"
docker build -t lab-web:1.0 . 2>&1 | tail -12

hr "2 镜像信息"
docker images lab-web --format '{{.Repository}}:{{.Tag}} {{.Size}}'
echo "--- 分层（docker history）"
docker history lab-web:1.0 --format '{{.CreatedBy}} | {{.Size}}'

hr "3 自定义网络 + redis + web（服务名通信）"
docker network create lab-net >/dev/null
docker run -d --name lab-cache --network lab-net redis:7-alpine >/dev/null
docker run -d --name lab-web --network lab-net -p 5000:5000 -e REDIS_HOST=lab-cache lab-web:1.0 >/dev/null
sleep 6
docker ps --filter name=lab- --format '{{.Names}}\t{{.Status}}\t{{.Ports}}'

hr "4 访问计数三次，验证 redis 在容器间被共享"
for i in 1 2 3; do
  echo "--- 第 $i 次访问"
  curl -s http://localhost:5000/
done
echo "--- /health"; curl -s http://localhost:5000/health; echo

hr "5 CMD vs ENTRYPOINT"
cd "$WORK"
cat > exp/Dockerfile.cmd <<'EOF'
FROM alpine:3.20
CMD ["echo", "default-cmd"]
EOF
cat > exp/Dockerfile.entry <<'EOF'
FROM alpine:3.20
ENTRYPOINT ["echo", "entry"]
EOF
cd "$WORK/exp"
docker build -q -f Dockerfile.cmd   -t lab-cmdtest   . >/dev/null
docker build -q -f Dockerfile.entry -t lab-entrytest . >/dev/null
echo "--- 只跑 CMD 镜像（用默认 CMD）";            docker run --rm lab-cmdtest
echo "--- 传入 echo override-cmd（覆盖 CMD）";     docker run --rm lab-cmdtest echo override-cmd
echo "--- ENTRYPOINT 镜像 + 参数 arg1";            docker run --rm lab-entrytest arg1
echo "--- --entrypoint 覆盖 ENTRYPOINT";           docker run --rm --entrypoint echo lab-entrytest -n hi; echo

hr "6 ARG vs ENV"
cat > Dockerfile.args <<'EOF'
FROM alpine:3.20
ARG BUILD_ARG=arg-default
ENV RUN_ENV=env-value
RUN echo "build-time sees BUILD_ARG=$BUILD_ARG"
EOF
docker build --build-arg BUILD_ARG=passed -f Dockerfile.args -t lab-argtest . 2>&1 | grep 'build-time' || true
echo "--- 运行时 env"; docker run --rm lab-argtest env | grep RUN_ENV
echo "--- 运行时读 BUILD_ARG（应为空，ARG 只在构建期存在）"
docker run --rm lab-argtest sh -c 'echo "runtime BUILD_ARG=[$BUILD_ARG]"'

hr "7 清理实验容器"
docker rm -f lab-web lab-cache >/dev/null 2>&1
echo "done"

hr "DONE stage02"
