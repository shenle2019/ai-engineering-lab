#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

echo "== 1. 时区 =="
ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime
echo "Asia/Shanghai" > /etc/timezone

echo "== 2. systemd 状态 =="
systemctl is-system-running || true
ps -p 1 -o comm= || true

echo "== 3. 安装 docker.io + docker-compose-v2 =="
apt-get install -y --no-install-recommends docker.io docker-compose-v2

echo "== 4. 国内镜像加速 =="
mkdir -p /etc/docker
cat > /etc/docker/daemon.json <<'EOF'
{
  "registry-mirrors": [
    "https://docker.m.daocloud.io",
    "https://docker.1ms.run",
    "https://docker.1panel.live"
  ],
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "3" }
}
EOF

systemctl enable docker
systemctl restart docker
sleep 4

echo "== 5. 校验 =="
systemctl is-active docker
docker version --format 'client={{.Client.Version}} server={{.Server.Version}}'
docker compose version
docker info --format 'driver={{.Driver}} mirrors={{range .RegistryConfig.Mirrors}}{{.}} {{end}}'
