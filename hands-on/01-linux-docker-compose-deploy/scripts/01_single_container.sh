#!/usr/bin/env bash
# 阶段 01：单容器部署 redis / nginx（对应预习2 day05 的应用部署与数据卷）
# 验证点：端口映射、目录/命名卷挂载、容器内数据持久化、日志与 exec
set -uo pipefail

WORK=/opt/lab/stage01
rm -rf "$WORK" 2>/dev/null; mkdir -p "$WORK/html"; cd "$WORK"

hr() { echo; echo "===== $* ====="; }

hr "0 清理历史容器与卷"
docker rm -f lab-redis lab-nginx >/dev/null 2>&1
docker volume rm redis_data >/dev/null 2>&1
echo "clean done"

hr "1 准备镜像"
docker pull nginx:alpine 2>&1 | tail -2

hr "2 启动 redis（命名卷 redis_data + 端口映射）"
docker run -d --name lab-redis \
  -p 6379:6379 \
  -v redis_data:/data \
  redis:7-alpine \
  redis-server --appendonly yes
sleep 4
docker ps --filter name=lab-redis --format '{{.Names}} {{.Status}} {{.Ports}}'

hr "3 写入数据并读取"
docker exec lab-redis redis-cli SET site luffycity
docker exec lab-redis redis-cli SET visits 1
docker exec lab-redis redis-cli GET site
echo "--- KEYS *"; docker exec lab-redis redis-cli KEYS '*'

hr "4 删除容器后重建，验证命名卷数据仍在"
docker rm -f lab-redis >/dev/null
echo "容器已删除，卷列表："; docker volume ls --format '{{.Name}} {{.Driver}}' | grep redis_data
docker run -d --name lab-redis -p 6379:6379 -v redis_data:/data redis:7-alpine redis-server --appendonly yes
sleep 4
echo "--- 重建后 GET site"; docker exec lab-redis redis-cli GET site
echo "--- 重建后 GET visits"; docker exec lab-redis redis-cli GET visits

hr "5 写入宿主机 html 并启动 nginx（目录映射 + 只读）"
cat > html/index.html <<'HTML'
<h1>hello from nginx container</h1>
<p>mounted from /opt/lab/stage01/html</p>
HTML
docker run -d --name lab-nginx \
  -p 8080:80 \
  -v /opt/lab/stage01/html:/usr/share/nginx/html:ro \
  nginx:alpine
sleep 3
echo "--- curl http://localhost:8080"; curl -s http://localhost:8080

hr "6 改宿主机文件，容器内立即生效（目录映射的意义）"
echo '<p>hot update by host</p>' >> html/index.html
echo "--- 再次 curl"; curl -s http://localhost:8080

hr "7 运维常用：logs / exec / inspect / stats"
docker logs --tail 3 lab-nginx
echo "--- 容器内看目录"; docker exec lab-nginx ls /usr/share/nginx/html
echo "--- 端口映射"; docker port lab-nginx
echo "--- IP 地址"; docker inspect lab-nginx --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'
echo "--- 资源占用(一次性)"; docker stats --no-stream --format '{{.Name}} cpu={{.CPUPerc}} mem={{.MemUsage}}'

hr "8 镜像与容器清单"
docker images --format '{{.Repository}}:{{.Tag}} {{.Size}}'
docker ps --format '{{.Names}}\t{{.Image}}\t{{.Ports}}'

hr "DONE stage01"
