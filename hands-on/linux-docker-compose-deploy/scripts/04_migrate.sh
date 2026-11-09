#!/usr/bin/env bash
# 阶段 04：镜像迁移与备份 commit / save / load（对应预习2 day05 的迁移备份）
# 验证点：容器快照成镜像、镜像导出为 tar、删除后从 tar 恢复并可用
set -uo pipefail

WORK=/opt/lab/stage04
rm -rf "$WORK" 2>/dev/null; mkdir -p "$WORK"; cd "$WORK"

hr() { echo; echo "===== $* ====="; }

hr "0 清理"
docker rm -f lab-snap >/dev/null 2>&1
docker rmi -f lab-snapshot:1.0 >/dev/null 2>&1
rm -f /tmp/lab-snapshot.tar
echo "clean done"

hr "1 起一个基础容器，在里面改东西"
docker run -d --name lab-snap alpine:3.20 sleep 300 >/dev/null
docker exec lab-snap sh -c 'echo "snapshot-marker" > /marker.txt; adduser -D appuser'
echo "--- 容器内改动"; docker exec lab-snap sh -c 'cat /marker.txt; id appuser'

hr "2 commit 把容器固化成镜像"
docker commit --change 'CMD ["cat","/marker.txt"]' lab-snap lab-snapshot:1.0
docker images lab-snapshot --format '{{.Repository}}:{{.Tag}} {{.Size}}'

hr "3 新镜像直接运行，确认改动被带上"
docker run --rm lab-snapshot:1.0

hr "4 save 导出为 tar（离线迁移用）"
docker save -o /tmp/lab-snapshot.tar lab-snapshot:1.0
ls -lh /tmp/lab-snapshot.tar | awk '{print $5, $9}'
echo "--- tar 内层结构"; tar tf /tmp/lab-snapshot.tar | head -6

hr "5 删除本地镜像，模拟目标机器没有该镜像"
docker rmi -f lab-snapshot:1.0 >/dev/null
docker images lab-snapshot --format '{{.Repository}}:{{.Tag}}' | wc -l

hr "6 load 从 tar 恢复镜像"
docker load -i /tmp/lab-snapshot.tar
docker images lab-snapshot --format '{{.Repository}}:{{.Tag}} {{.Size}}'

hr "7 恢复后运行验证"
docker run --rm lab-snapshot:1.0

hr "8 业务镜像同样可以整体迁移（lab-web:1.0）"
docker save -o /tmp/lab-web.tar lab-web:1.0
echo "--- lab-web tar 大小"; ls -lh /tmp/lab-web.tar | awk '{print $5}'
docker load -i /tmp/lab-web.tar 2>&1 | tail -2

hr "9 清理临时文件与容器"
docker rm -f lab-snap >/dev/null 2>&1
rm -f /tmp/lab-snapshot.tar /tmp/lab-web.tar
echo "cleaned"

hr "DONE stage04"
