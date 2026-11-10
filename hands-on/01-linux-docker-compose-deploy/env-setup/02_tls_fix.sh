#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

SRC="/etc/apt/sources.list.d/ubuntu.sources"
[ -f "$SRC" ] || SRC="/etc/apt/sources.list"

echo "== 1. 暂时切回 http 源 =="
sed -i 's|https://mirrors.tuna.tsinghua.edu.cn/ubuntu|http://mirrors.tuna.tsinghua.edu.cn/ubuntu|g' "$SRC"
grep -m2 'URIs\|^deb ' "$SRC" || true

echo "== 2. update (http) =="
apt-get update -y

echo "== 3. 安装 ca-certificates =="
apt-get install -y --no-install-recommends ca-certificates

echo "== 4. 切回 https 源 =="
sed -i 's|http://mirrors.tuna.tsinghua.edu.cn/ubuntu|https://mirrors.tuna.tsinghua.edu.cn/ubuntu|g' "$SRC"
apt-get update -y

echo "== 5. 基础工具 =="
apt-get install -y --no-install-recommends curl iproute2 iputils-ping vim less procps sudo net-tools tree tar gzip unzip git

echo "== 6. 校验 =="
curl -sI https://mirrors.tuna.tsinghua.edu.cn | head -1
which curl vim git tree sudo | cat
