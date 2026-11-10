#!/usr/bin/env bash
set -euo pipefail

echo "== 1. wsl.conf =="
cat > /etc/wsl.conf <<'EOF'
[boot]
systemd=true

[network]
generateResolvConf=true

[interop]
enabled=true
EOF

echo "== 2. apt sources -> tuna =="
for f in /etc/apt/sources.list.d/ubuntu.sources /etc/apt/sources.list; do
  if [ -f "$f" ]; then
    sed -i 's|http://archive.ubuntu.com/ubuntu|https://mirrors.tuna.tsinghua.edu.cn/ubuntu|g; s|http://security.ubuntu.com/ubuntu|https://mirrors.tuna.tsinghua.edu.cn/ubuntu|g' "$f"
    echo "patched: $f"
  fi
done

echo "== 3. dns check =="
getent hosts mirrors.tuna.tsinghua.edu.cn | head -2 || true

echo "== 4. apt update =="
export DEBIAN_FRONTEND=noninteractive
apt-get update -y

echo "== 5. base packages =="
apt-get install -y --no-install-recommends ca-certificates curl iproute2 iputils-ping vim less procps sudo net-tools tree

echo "== 6. version =="
cat /etc/os-release | head -2
curl -sI https://mirrors.tuna.tsinghua.edu.cn | head -1
