#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

echo "== 1. 安装 systemd =="
apt-get install -y --no-install-recommends systemd systemd-sysv dbus

echo "== 2. 确认 wsl.conf =="
cat /etc/wsl.conf

echo "== 3. 确认 systemd 二进制 =="
ls -l /lib/systemd/systemd
/usr/bin/systemctl --version | head -1

echo "== 4. docker 包清单 =="
dpkg -l | awk '/docker/ {print $2, $3}'
