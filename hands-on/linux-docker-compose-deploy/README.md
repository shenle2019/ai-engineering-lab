# Linux + Docker + Compose 部署访问计数应用

预习部分（预习1 Linux 入门、预习2 Docker 从入门到精通、预习3 Docker Compose 详解）的整合实操。
把三份课件里的零散命令串成一条可重跑的部署链路：**Linux 基础操作 → 单容器 → Dockerfile 构建 → Compose 编排 → 镜像迁移**。

## 案例主线

```
Linux 命令/权限/链接
        │
        ▼
redis 单容器（命名卷持久化）   nginx 单容器（目录映射热更新）
        │
        ▼
Dockerfile 构建 Flask 访问计数应用  ──►  容器间通过服务名通信
        │
        ▼
Compose 编排 redis + web + nginx（nginx 反代 web:5000）
        │
        ▼
commit / save / load 把镜像搬到另一台机器
```

最终产物：访问 `http://localhost:8088`，每刷新一次计数 +1，计数存在 redis 命名卷里，重建编排后继续累加。

## 运行环境（本机实测）

| 项 | 值 |
| --- | --- |
| 系统 | Windows 10 22H2 + WSL2，发行版 Ubuntu 24.04.5 LTS（rootfs 离线导入，装在 D 盘） |
| 内核 | 6.18.54.1-microsoft-standard-WSL2 |
| Docker | Engine 29.1.3，存储驱动 overlayfs，systemd 托管 |
| Compose | v2.40.3（`docker compose` 插件） |
| 镜像加速 | docker.m.daocloud.io / docker.1ms.run / docker.1panel.live |
| apt 源 | 清华（mirrors.tuna.tsinghua.edu.cn） |

课件用的是 CentOS + VMware + `yum/dnf`，这里用 Ubuntu + WSL2 + `apt`，命令语义一一对应（`dnf install` ↔ `apt install`，`systemctl` 完全一致）。

### 从零搭建这套环境

本机初始状态：没有 Docker、没有 Linux 发行版（WSL 功能已启用但无 distro）、VMware 未安装、Docker Hub 不可达。搭建步骤（脚本已归档在 `env-setup/`）：

1. 下载 Ubuntu base rootfs（清华源）并校验 SHA256：
   `https://mirrors.tuna.tsinghua.edu.cn/ubuntu-cdimage/ubuntu-base/releases/24.04/release/ubuntu-base-24.04.5-base-amd64.tar.gz`
2. 导入为 WSL 发行版：`wsl --import ubuntu-24.04 D:\wsl\ubuntu-24.04\instance <rootfs.tar.gz> --version 2`
3. `env-setup/01_base.sh`：写 `/etc/wsl.conf` 开 systemd、apt 换清华源、装基础工具
4. `env-setup/02_tls_fix.sh`：先用 HTTP 源装 `ca-certificates`，再切回 HTTPS（rootfs 不带根证书，直接连 HTTPS 源会卡死）
5. `env-setup/04_systemd.sh`：补装 `systemd systemd-sysv dbus`（ubuntu-base 极简镜像不带）
6. `env-setup/03_docker.sh`：装 `docker.io` + `docker-compose-v2`，写镜像加速 `daemon.json`，`systemctl enable docker`
7. `wsl --terminate ubuntu-24.04` 让 systemd 接管 PID 1，再进发现 `systemctl is-active docker` = active

第 4、5 步互不依赖，但都必须在第 6 步之前完成。

## 目录结构

```
.
├── app/                        Flask 访问计数应用
│   ├── app.py                  GET / 计数 +1，GET /health 探活
│   ├── requirements.txt        flask、redis
│   └── Dockerfile              python:3.12-slim，分层构建
├── compose/
│   ├── docker-compose.yml      redis + web + nginx 三服务
│   └── nginx/default.conf      proxy_pass http://web:5000
├── scripts/
│   ├── 00_linux_basics.sh      文件/权限/软硬链接/用户/压缩/服务/进程/vim
│   ├── 01_single_container.sh  redis、nginx 单容器与数据卷
│   ├── 02_dockerfile.sh        构建应用镜像 + CMD/ENTRYPOINT/ARG/ENV/分层实验
│   ├── 03_compose.sh           编排启动、服务名通信、healthcheck、重启验卷
│   ├── 04_migrate.sh           commit / save / load
│   └── run_all.sh              一键串跑，日志写到 logs/
├── env-setup/                  WSL2 + Ubuntu + Docker 环境从零搭建脚本
│   ├── 01_base.sh              wsl.conf / apt 源 / 基础工具
│   ├── 02_tls_fix.sh           HTTP 源装证书后切回 HTTPS
│   ├── 03_docker.sh            docker.io + compose + 镜像加速
│   └── 04_systemd.sh           补装 systemd
└── logs/                       每个阶段的真实运行日志
```

## 各阶段验证点与结果

### 00 Linux 基础（日志 `logs/00_linux_basics.log`）

| 验证点 | 结果 |
| --- | --- |
| cat / tail / grep / wget / curl | 文件读取与下载正常，wget 下载 SHA256SUMS 得 18 行 |
| 权限位 | `chmod 640` → `-rw-r-----`，`umask=0022`，目录 750 |
| 软硬链接 | 硬链接与原文件 inode 相同（12603），链接数 2；软链接是独立 inode 指向源文件 |
| 删除源文件 | 硬链接内容仍在；软链接变断链（`readlink` 显示指向已删除文件） |
| 用户 | `useradd luffy` 后 uid=1000，`chown luffy:luffy` 生效 |
| 压缩解压 | `tar czf` → `tar tzf` 列表 → `tar xzf -C` 解压三件套 |
| 服务 | `systemctl is-active docker` = active |
| 进程 | `ps aux` 找到 dockerd，PID 123 |
| vim | 非交互写入并读回 `hello from vim` |

### 01 单容器（日志 `logs/01_single_container.log`）

| 验证点 | 结果 |
| --- | --- |
| redis 命名卷 | `-v redis_data:/data`，AOF 开启 |
| 数据持久化 | 删除容器后重建，`GET site` 仍为 `luffycity`、`GET visits` 仍为 `1` |
| nginx 目录映射 | `-v /opt/lab/stage01/html:/usr/share/nginx/html:ro`，改宿主机文件后 `curl` 立即看到 `hot update by host` |
| 运维命令 | logs / exec / port / inspect / stats 全部输出正常 |

### 02 Dockerfile（日志 `logs/02_dockerfile.log`）

| 验证点 | 结果 |
| --- | --- |
| 构建 | `docker build -t lab-web:1.0` 成功，分层里能看到 COPY requirements → RUN pip → COPY app.py 各一层 |
| 服务名通信 | 自定义网络 lab-net 上 `-e REDIS_HOST=lab-cache`，三次访问计数 1、2、3 |
| 健康检查 | `/health` 返回 `{"redis":true,"status":"ok"}` |
| CMD vs ENTRYPOINT | CMD 可被 `docker run img echo x` 覆盖；ENTRYPOINT 会把参数追加成 `entry arg1`；`--entrypoint` 可整体替换 |
| ARG vs ENV | 构建期 `BUILD_ARG=passed` 可见；运行时 `BUILD_ARG` 为空、`RUN_ENV=env-value` 可见 |

### 03 Compose（日志 `logs/03_compose.log`）

| 验证点 | 结果 |
| --- | --- |
| 文件校验 | `docker compose config --quiet` 通过 |
| 一键启动 | `up -d --build` 拉起 redis / web / nginx 三容器 |
| 反代链路 | `curl localhost:8088` → nginx → `web:5000` → redis，计数 1、2、3 |
| 服务名解析 | web 容器内 `socket.gethostbyname('redis')` = 172.20.0.2 |
| healthcheck 依赖 | `depends_on.condition: service_healthy`，redis `health=healthy` 后 web 才启动 |
| 重启不丢数据 | `down` 后再 `up`，第四次访问计数为 4，卷 `lab_compose_redis_data` 保留 |

### 04 迁移备份（日志 `logs/04_migrate.log`）

| 验证点 | 结果 |
| --- | --- |
| commit 固化 | 容器内写 `/marker.txt`、建 appuser，commit 成 `lab-snapshot:1.0`（12.2MB），镜像直接运行输出 `snapshot-marker` |
| save | 导出 tar，内层是 manifest + 层目录 |
| 删镜像后 load | `docker rmi` 删掉本地镜像，`docker load -i` 恢复成功，运行结果一致 |
| 业务镜像 | `lab-web:1.0` 同样可 save/load 完成整机迁移 |

## 运行方式

本机（Windows）侧只需保证 WSL 发行版和 Docker 服务已就绪：

```powershell
wsl -d ubuntu-24.04 -- bash /mnt/e/ailearning/python-luffycity/ai-engineering-lab/hands-on/linux-docker-compose-deploy/scripts/run_all.sh
```

或者进入 WSL 里单独跑某个阶段：

```bash
bash scripts/03_compose.sh
```

脚本会把项目拷到 `/opt/lab/stageXX` 运行，避免在 `/mnt/e`（9p 文件系统）上构建慢；仓库里只保留源码、配置和日志。

## 踩坑记录

1. **Docker Hub 不可达**：`registry-1.docker.io:443` 连接失败，`docker pull` 超时。解法是 `/etc/docker/daemon.json` 配三个国内 `registry-mirrors`，之后 `redis:7-alpine`、`nginx:alpine`、`python:3.12-slim` 都能正常拉取。
2. **Ubuntu base rootfs 没有 ca-certificates**：换 HTTPS 清华源后 apt 报 `Certificate verification failed: The certificate is NOT trusted`，装包又因为没有源索引而失败，死循环。解法是先用 HTTP 源 `apt-get update` 装 `ca-certificates`，再切回 HTTPS。
3. **ubuntu-base 不带 systemd**：`/etc/wsl.conf` 写了 `[boot] systemd=true` 也没用，PID 1 仍是 `init`，`systemctl: not found`。解法是补装 `systemd systemd-sysv dbus` 后 `wsl --terminate` 重启实例。
4. **`docker inspect {{.NetworkSettings.IPAddress}}` 返回空**：Docker 29 里未指定网络的容器该字段不存在，报 `map has no entry for key "IPAddress"`。改用 `{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}`。
5. **脚本内相对路径失效**：`02_dockerfile.sh` 在 `cd $WORK/app` 之后写 `exp/Dockerfile.cmd`，实际路径是 `$WORK/app/exp`，文件没写成，后面 `docker build` 直接失败。修法是写入前显式 `cd "$WORK"`。
6. **容器时区是 UTC**：nginx 日志时间比宿主机早 8 小时，排查时容易看错。需要一致时在服务里加 `TZ=Asia/Shanghai` 或挂载 `/etc/localtime`。

## 与课件的取舍

- 课件用 `docker commit` 讲镜像来源，这里保留并跑通，但应用本身用 Dockerfile 构建——commit 产物不可复现、体积不可控，只适合救急和留证。
- 课件 `yum install lrzsz` 传文件，WSL 环境直接用 `/mnt/e` 挂载与 `curl/wget`，未复刻 rz/sz（需要交互式终端）。
- 课件里路飞项目、图书管理系统属于后续 day06 内容，本次预习复刻只做通用链路，未引入这两个业务项目。
