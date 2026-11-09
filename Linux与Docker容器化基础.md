# Linux 与 Docker 容器化基础

> 来源课件：
> - `E:\ailearning\python-luffycity\python山顶会三期\预习1-Linux入门操作\day04-Linux入门操作-仅课件.zip`（day04 课堂笔记）
> - `E:\ailearning\python-luffycity\python山顶会三期\预习2-Docker从入门到精通.zip`（day05 课堂笔记）
> - `E:\ailearning\python-luffycity\python山顶会三期\预习3-Docker-compose详解-仅笔记.zip`（day06 课堂笔记）
> - 软件包：预习2 的 `snake.zip` / Navicat，预习3 的 node、Redis 客户端、resp、`books-master.zip`、`luffy.zip`
>
> 本文是理解向提炼，不复制课件代码，不含验证结论。

## 0 总览

预习三课其实是一条完整的部署主线：

```
Linux 命令基础（会操作机器）
   → 用户/权限/软件包/服务/进程（会管理机器）
      → Docker 单容器（会跑软件，环境一致）
         → Dockerfile（会造镜像，可交付）
            → Docker Compose（会编排多服务，一键部署）
```

一句话概括：**从"裸机手工装环境"走到"一个配置文件拉起整套服务"**。后面 AI 项目的 Dify、向量库、数据库部署，都是这条线的复用。

## 1 操作系统与 Linux 定位

- OS 三平台（Windows / macOS / Linux）软件互不兼容，全平台软件是分别发布的三个包。
- 个人用 Windows 图形化，mac 介于两者之间（命令兼容 Linux + 有图形界面），**企业部署 99% 用 Linux**，几乎纯命令。
- BootLoader：开机后先跑引导程序再进内核；多系统时由 GRUB 选择默认系统，几秒不选则进默认。安卓手机上的 BL 锁就是厂商限制刷机的同一层机制。

### 1.1 谱系脉络（理解发行版混乱的根源）

| 时间 | 事件 |
| --- | --- |
| 1970 | Unix 诞生（贝尔实验室，汇编实现，源于 Multics 项目流产后的副产品） |
| 1973 | 用 C 重写 Unix，摆脱硬件依赖，可移植 |
| 1984 | RMS 创立 GNU 项目（GNU is not Unix），自由软件运动，产出 Emacs/GCC/GDB |
| 1991 | Linus 发布 Linux 内核 0.0.1（当时把 Unix 源码改了放学校网站） |

- **Linux 发行版 = Linux 内核 + GNU 工具 + 厂商自己的软件**。内核是骨骼，GNU 是血肉。
- 内核版本用 `uname -r` 看，如 `5.15.0-88-generic`：主版本.次版本.修订号 - 发行版补丁 - 编译目标平台。
- 自由软件 ≠ 免费：自由指源码必须公开、可复制修改出售；RedHat 收费卖的是服务，源码仍必须开源。

### 1.2 发行版四系

| 系 | 包格式 / 包管理 | 代表 | 特点 |
| --- | --- | --- | --- |
| Debian 系 | deb / apt | Debian、Ubuntu（桌面+服务器）、Deepin | 最遵循 GNU 规范 |
| RHEL 系 | rpm / yum、dnf | RHEL（收费）、CentOS（8 后停更）、Rocky（CentOS 创始人另起，主流替代）、CentOS Stream（RHEL 上游滚动版） | 企业服务器主力 |
| SUSE 系 | rpm / zypper | SLES | 欧洲多，国内少 |
| 国产系 | deb 或 rpm | 统信 UOS、银河麒麟、优麒麟、龙蜥、openEuler、红旗 | 信创场景，桌面多为 Debian 系 |

- 不同发行版差异只在：安装方式、包管理器、预装软件；**约 85% 命令通用**，内核可能版本不同。
- 选型结论：企业要免费又稳定 → Rocky Linux / CentOS 兼容路线。

## 2 环境搭建

- **先看 CPU 架构再下载安装包**：个人机基本是 x86_64（Intel/AMD）或 AArch64（ARM、鲲鹏、Apple M）；服务器还有 PPC64LE、s390x。架构不对，装包必失败。
- VMware Workstation 只支持 Windows/Linux；mac 用 VMware Fusion 或 Parallels。
- 虚拟机配置参考：4 CPU × 2 核、16G 内存、50G 硬盘，够学完整套课程。
- 镜像下载：官方 `mirror.stream.centos.org`，国内用阿里云镜像站加速；教学用 CentOS Stream 9。
- 远程连接：`ip addr` 查 IP，用 FinalShell（免费跨平台，集成了终端 + 文件管理）替代 xshell/Termius；本质等价于 `ssh root@ip`。
- 快照 = 系统存档，随时回滚；克隆 = 基于模板机复制多台，搭集群不用重复装系统。**装好的第一台永远不动，只做模板**。
- 云服务器 = 放在别人机房的机器，同样是 ssh 登录；后期跑大模型再按需买带显卡的机型。

## 3 Shell 基础

Shell 是命令解释器（类比 Python 解释器），处在内核外层，把命令翻译给系统并回显结果。远程工具连上就是打开一个 shell 窗口。

### 3.1 语法与效率操作

- 命令格式：`command [-options] [arguments]`，选项和参数可省，命令必须有。
- `ls -a` 显示隐藏文件，`ls -l` 长格式，`ls -al` 两者合并；`ll` 等价 `ls -l`。
- Tab 补全；Ctrl+A/E 行首行尾、Ctrl+C 终止前台、Ctrl+Z 挂后台、Ctrl+L 清屏、Ctrl+U/K 删到行首/行尾、Ctrl+R 搜历史。
- history：`!!` 上一条、`!n` 第 n 条、`!前缀` 最近一次匹配；`history -c` 只清内存，文件在 `~/.bash_history`，需要 `> .bash_history` 才真清。
- alias 只在当前会话生效；永久写 `~/.bashrc`（当前用户）或 `/etc/bashrc`（全员）。

### 3.2 内置命令、外部命令与环境变量

- 内置命令由 shell 自带；外部命令要装软件才有，例如 `ifconfig` 属于 net-tools，CentOS 默认没有，`ip addr` 才是自带的。
- 环境变量是 KEY=VALUE 的全局配置：`env` 全看，`echo $USER` / `echo $PATH` 单看。
- **PATH 是可执行程序的搜索路径列表**。命令找不到，第一反应就是它所在目录没进 PATH；解决方式是改 PATH，或在已在 PATH 的 `/usr/bin` 下建软链接。
- 用户变量（`~/.bashrc`、`~/.bash_profile`）优先于系统变量（`/etc/profile`、`/etc/bashrc`），同名覆盖。

### 3.3 用户与提权

- `id` 看 uid/gid：**uid=0 是 root**，1~200 系统自带服务账号，201~999 装软件创建的服务账号，1000+ 才是可登录的普通用户。
- 常用：`useradd` / `passwd` / `usermod -L|-U`（锁/解锁）/ `userdel -r`（连家目录一起删）。
- 服务账号不需要登录：`useradd mysql -M -s /sbin/nologin`。
- `su`：root 切普通用户免密，普通用户切 root 要 root 密码；`sudo`：按授权临时提权，能否成功取决于是否被授予。
- 家目录：root 在 `/root`，普通用户在 `/home/用户名`，普通用户互相看不到对方家目录。

## 4 文件系统与日常命令

### 4.1 目录结构（记用途，不记全部）

| 目录 | 用途 |
| --- | --- |
| `/bin` `/sbin` | 普通用户 / 管理员的命令，见到 bin 就想到可执行文件 |
| `/usr` | 相当于 `C:\Windows`；`/usr/local` 相当于 `C:\Program Files`，自己装的软件放这里 |
| `/etc` | 所有服务配置，改配置来这里 |
| `/var/log` | 日志，如 `/var/log/secure` 记录登录 |
| `/proc` | 进程实时状态，每个 pid 一个目录，进程结束目录消失；pid 1 是 systemd |
| `/dev` | 设备文件：`/dev/sd*` 硬盘、`/dev/null` 黑洞、`/dev/zero`、`/dev/random` |
| `/run` | 运行时 pid、lock 文件，如 `/run/yum.pid` |
| `/opt` | 第三方软件安装位；`/media` `/mnt` 挂载点；`/tmp` 公共临时目录 |
| `/home` `/root` | 普通用户 / root 的家目录 |

### 4.2 路径与文件操作

- 绝对路径从 `/` 开始；相对路径靠 `.`（当前）和 `..`（上级）；`cd -` 回上一次目录，`cd ~` 回家。
- 建：`touch` 建文件（存在则改时间）、`mkdir -p` 递归建、`mkdir -v` 显示过程。
- 复制移动：`cp -r` 复制目录、`-p` 保留属性、`-v` 显示过程；`mv` 兼改名。
- 删除：`rm -r` 递归、`rm -f` 强制。**`rm -rf /` 是事故级命令，`rm -rf *` 前先确认当前目录。**
- 查看：`cat` 全量、`tail -f` 跟踪日志、`grep` 过滤、`|` 管道把前一个命令输出喂给后一个。
- 下载上传：`wget -O` 下载文件；`curl -o` 也能下载，但重点是模拟 HTTP 请求（`-X` 方法、`-H` 头、`-d` 请求体）；`rz`/`sz` 走 lrzsz 传小文件（≤4G，不能传目录）。
- 压缩：**Windows 与 Linux 互传用 zip**（rar 在 Linux 上解不了）；`zip -r` / `unzip -d`；Linux 原生用 tar：`tar czf` 打包、`tar xvf` 解压、`tar tf` 查看内容。

### 4.3 文件属性与权限

`-rw-r--r-- 1 root root 39 Dec 28 14:12 lqz.txt` 拆读：

- 第 1 位文件类型：`-` 普通、`d` 目录、`l` 链接、`b` 块设备、`c` 字符设备、`s` socket、`p` 管道。
- 后 9 位三组：属主 / 属组 / 其他人，每组 `rwx`。
- 后面依次是硬链接数、属主、属组、大小、最后修改时间、文件名。

改权限两种写法：

- 符号法：`chmod u=rwx,g=rw,o=r 文件`，`chmod +x 文件` 给所有人加执行权限。
- 数字法：r=4、w=2、x=1，三位相加。`755` = rwxr-xr-x，`644` 是文件常态。

特殊属性：`chattr +i 文件` 锁定不可改不可删，`chattr -i` 解锁。应急场景：机器中毒时先定位高占用进程对应的可执行文件，删不掉就是被加了 i 属性。

### 4.4 软链接与硬链接

```
文件名  → inode（类型/大小/位置/时间）→ block（真实数据）
```

- **软链接**（`ln -s 源 目标`）：相当于 Windows 快捷方式，新建一个 inode 指向源文件路径；源文件删了，链接失效。
- **硬链接**：同一个 inode 起多个文件名，删掉其中一个只是少个名字，数据还在；不能跨分区。
- 实战用途：软件装在 `/usr/local/xxx/bin` 没进 PATH，就在 `/usr/bin` 里做软链，任意位置可直接敲命令。

### 4.5 vim 三模式

- 普通模式（默认）：`gg` 顶部、`G` 底部、`yy` 复制行、`dd` 删行、`p` 粘贴、`u` 撤销、`r` 替换单字符。
- 编辑模式：从普通模式按 `i`（光标不动）/ `a`（后移一位）/ `o`（下行插空行）进入，Esc 回普通模式。
- 命令模式：普通模式输入 `:` 进入，`:wq` 存退、`:q!` 强退、`:set nu` 显示行号、`:n` 跳行。
- 残留 `.<文件名>.swap` 说明上次异常退出，可直接删掉，不再提示。

### 4.6 软件管理、服务与进程

- 包管理：CentOS 9 用 `dnf`（Python3 写的，`yum` 只是软链接到 dnf），安装 `dnf install -y`、卸载 `dnf remove`。仓库里版本固定，要最新版得源码安装。
- 服务：`systemctl start|stop|status|reload|enable|disable 服务名`；`enable` 才是开机自启。
- 源码装的软件默认不被 systemctl 管理，需自建 service 文件放 `/usr/lib/systemd/system/`，其中 `ExecStart/ExecStop/ExecReload` 指向自身二进制。
- 进程：`ps aux` 看全部（USER/PID/%CPU/%MEM/COMMAND），`ps aux | grep 名字` 查是否在跑，`top` 动态看，`kill -9 pid` 强杀，`pkill -9 名字` 批量杀。
- 服务运行身份要注意：nginx 以 nginx 用户跑，网站文件放在 root 目录下就访问不到，必须放 `/usr/share/nginx/html` 这类有权限的位置。

## 5 Docker 单容器

### 5.1 为什么用

- 解决"环境不一致"：应用连同依赖（代码、运行时、库、配置）一起打包成镜像，换机器照样跑。
- **镜像 ≈ 类，容器 ≈ 对象**：一个镜像可以跑出多个容器。
- 容器 ≈ 超轻量虚拟机（Linux + 一个软件），有独立网络，与宿主机隔离；比裸机装的优势是快、统一、崩了不影响宿主机、不挑宿主机系统。

### 5.2 安装与国内镜像

- CentOS 安装：先 `dnf config-manager --add-repo` 加阿里云的 docker-ce 仓库，再 `dnf install docker-ce docker-ce-cli containerd.io docker-compose-plugin -y`，最后 `systemctl start docker`。
- Docker Hub 国内访问不通，必须配镜像加速：编辑 `/etc/docker/daemon.json` 写 `registry-mirrors` 与 `insecure-registries`，然后 `systemctl daemon-reload` + `systemctl restart docker`。
- 更省事的单源方案：只配 `https://docker.1ms.run`，或用其拉取前缀 `docker pull docker.1ms.run/nginx:latest`。

### 5.3 镜像与容器操作

| 操作 | 命令 |
| --- | --- |
| 搜索 | `docker search mysql`（或直接去 hub 网站看） |
| 拉取 | `docker pull mysql:8.0.40-debian`（不写 tag 默认 latest） |
| 查看镜像 | `docker images` |
| 删镜像 | `docker rmi 镜像:tag`（先删干净容器才能删） |
| 跑容器 | `docker run -id --name xx 镜像`（后台）/ `-it`（进交互） |
| 查容器 | `docker ps` / `docker ps -a` |
| 进容器 | `docker exec -it 容器名 /bin/bash` |
| 启停删 | `docker start/stop 容器`、`docker rm 容器`（运行中删不掉，`-f` 强制） |

`run` 关键参数：

- `-i` 交互、`-t` 分配终端（`-it` 一起用才进得去）、`-d` 后台守护运行。
- `--name` 指定容器名，不指定随机。
- `-p 宿主机端口:容器端口`，可以多组。
- `-v 宿主机目录:容器目录`，**目录映射是数据不丢的前提**。

两个高频坑：

- `-it` 启动后 `exit`，容器随之停止且再也进不去；用 `-id` 起、`exec` 进，`exit` 不影响容器。
- 不做 `-v` 映射的数据库容器，删除即数据全丢。

### 5.4 三个部署案例

- **MySQL**：`-p 3308:3306 -e MYSQL_ROOT_PASSWORD=xxx`，同时映射 `/var/lib/mysql`（数据）、`/etc/mysql/conf.d`、`/etc/mysql/my.cnf`（配置）。删容器重建、重新映射同一目录，数据仍在。宿主机装 Navicat 连 3308 即可。
- **Redis**：配置文件里 `bind 0.0.0.0` 才允许远程访问（写 127.0.0.1 只能本机）、`requirepass` 设密码；容器启动命令追加 `redis-server /etc/redis/redis.conf`，并映射 `/data` 做持久化。Redis 是内存型 KV 存储，读写不走磁盘 IO，主要做缓存。
- **Nginx**：`-p 8008:80 -v /home/html:/usr/share/nginx/html`，宿主机放页面文件即可访问，静态站点部署只需这一条命令。

## 6 镜像制作与迁移

镜像四个来源：`pull` 拉取、`commit` 把容器打包、`build` 按 Dockerfile 构建（最主流）、`load` 从 tar 恢复。

### 6.1 commit 与 save/load

- `docker commit 容器名 新镜像名`：把当前容器（含改动，比如装了 vim）打成新镜像，之后基于它跑的容器自带这些改动。
- `docker save -o xxx.tar 镜像名` 导出，`docker load -i xxx.tar` 导入。离线交付/换机器用这个，但要注意镜像体积大、无法追溯构建过程。

### 6.2 Dockerfile 指令

```dockerfile
FROM python:3.11                    # 基础镜像
LABEL maintainer="xxx"              # 作者（MAINTAINER 已废弃）
WORKDIR /soft                       # 工作目录，不存在会自动创建
COPY ./requirements.txt /soft/      # 拷贝，不自动解压
ADD  ./pkg.tar.gz /soft/            # 拷贝，能解压特定格式、能拉 URL
RUN pip install -r requirements.txt # 构建时执行，可多条
ENV TZ=Asia/Shanghai                # 构建+运行都生效
ARG VERSION=1.0                     # 只在构建期生效
EXPOSE 8080                         # 声明端口（仅是声明）
CMD ["python","app.py"]             # 容器启动命令，可被 run 命令覆盖
```

- `CMD` 与 `ENTRYPOINT`：都只在 `docker run` 时执行，多条只有最后一条生效；ENTRYPOINT 不会被 `run` 后的命令覆盖，CMD 会被覆盖；两者同用时 CMD 的内容会作为 ENTRYPOINT 的参数。
- `ENV` 与 `ARG`：ENV 构建完仍存在，ARG 构建完消失。

### 6.3 分层与构建

- 每条指令构建一层，`docker history 镜像名` 可看分层。
- 分层让分发增量下载；因此**多条相关命令尽量用 `&&` 合并成一条 RUN**，减少层数。
- 构建时本质是临时起一个容器逐条执行指令，最后打包成镜像。
- 构建与运行：

```bash
docker build -t django_books .      # 基于当前目录 Dockerfile 构建
docker run -id --name books -v /root/books:/soft -p 8080:8080 django_books
```

- 注意：Dockerfile 里只 COPY 了依赖清单，项目代码靠 `-v` 目录映射进去，改宿主机即改容器。若把代码 COPY 进镜像，则改代码要重新 build。

## 7 Docker Compose 多容器编排

- 定位：**单机**容器编排（3~5 个容器），一条命令拉起整套服务；多机成百上千容器才上 k8s。
- 两个核心概念：服务（Service，一个服务对应一个容器定义）、项目（Project，一个 compose 文件管理的一组服务）。
- 原则：一个容器一个服务，不要把所有服务塞进一个容器。

### 7.1 常用命令

| 命令 | 作用 |
| --- | --- |
| `docker compose up` | 创建并启动所有服务（`-d` 后台；`-f` 指定文件） |
| `docker compose down` | 停止并删除容器、网络、卷 |
| `docker compose stop` / `start` | 只停 / 启，不删 |
| `docker compose ps` / `logs` | 看状态 / 日志 |
| `docker compose build` | 重建镜像 |
| `docker compose up -d --build` | 重建镜像并启动 |
| `docker compose exec 服务名 bash` | 进容器 |

### 7.2 compose 文件骨架

```yaml
version: "3"
services:
  redis:
    image: redis:8.4.0
    container_name: luffy_redis
    ports: ["6379:6379"]
    volumes:
      - ./conf/redis.conf:/etc/redis/redis.conf
      - ./data:/data
    command: redis-server /etc/redis/redis.conf
    networks: [web]

  django:
    build:
      context: ./luffy_api
      dockerfile: Dockerfile
    ports: ["8080:8080"]
    volumes: ["./luffy_api:/soft"]
    environment: ["TZ=Asia/Shanghai"]
    env_file: ["./mysql.env"]
    depends_on: [mysql, redis]
    restart: always
    networks: [web]

networks:
  web:
```

- `depends_on` 只保证启动顺序，不保证依赖服务已就绪。
- `restart: always` 让容器挂了自动重启。
- **服务间通信用服务名当主机名**（如 flask 代码里 `Redis(host='redis')`），不用 IP；同一 network 内自动 DNS 解析。

### 7.3 两个案例

- **Flask + Redis 访问计数**：4 个文件（app.py、requirements.txt、Dockerfile、docker-compose.yml）。`docker compose up` 后自动构建 web 镜像、拉取 redis 镜像、建网络，web 里用服务名连 redis，做 incr 计数。`ports 8080:5000` 对外暴露。
- **路飞项目四容器**：nginx（前端 dist 静态文件 + `default.conf`）、django（自带 Dockerfile，`uwsgi luffy.ini` 启动）、redis、mysql（env_file 传密码，映射 data/logs/conf）。前端需先 `npm install && npm run build` 生成 dist 再上传；服务器上 `git clone` 后 `docker compose up` 一键起。
- 交付链路：开发改代码 → 编译前端 → 推到 git / 打包上传 → 运维 clone → compose up。运维侧不需要懂项目细节，这是容器化的核心价值。

## 8 速查命令表

| 分类 | 命令 | 说明 |
| --- | --- | --- |
| 系统 | `uname -r` | 内核版本 |
| 系统 | `ip addr` / `hostname` / `whoami` / `id` | 网络与身份 |
| 服务 | `systemctl start\|stop\|status\|enable 服务` | 服务管理 |
| 进程 | `ps aux \| grep x` / `top` / `kill -9 pid` | 进程管理 |
| 文件 | `ls -al` / `cp -r` / `rm -rf` / `mkdir -p` | 增删查改 |
| 权限 | `chmod 755 f` / `chown` / `chattr +i f` | 权限与锁定 |
| 链接 | `ln -s 源 目标` | 软链接 |
| 打包 | `zip -r` / `unzip` / `tar czf` / `tar xvf` | 压缩解压 |
| 软件 | `dnf install\|remove -y` | 包管理 |
| Docker | `docker pull/images/rmi` | 镜像 |
| Docker | `docker run -id --name n -p h:c -v h:c image` | 起容器 |
| Docker | `docker ps -a` / `exec -it n bash` / `stop` / `rm` | 容器 |
| Docker | `docker commit` / `save` / `load` / `build -t` | 造镜像与迁移 |
| Compose | `docker compose up -d` / `down` / `logs` / `exec` | 编排 |

## 9 踩坑清单

- 命令找不到 → PATH 没含该目录；装完软件要配 PATH 或做软链。
- 普通用户 `ls` 报 Permission denied → 目标在 root 家目录，属主权限问题。
- `rm -rf *` 前不 `pwd` 确认，删错目录；`rm -rf /` 直接报废机器。
- `-it` 起的容器 `exit` 就停且进不去 → 用 `-id` + `exec`。
- 数据库容器不 `-v` → 删容器数据全丢。
- `docker rmi` 报错 → 还有容器（含已停止的）引用该镜像，先 `rm` 容器。
- 拉镜像超时 → 镜像站没配或失效，换 `docker.1ms.run`。
- Redis 远程连不上 → `bind` 写成了 127.0.0.1。
- nginx 访问 403 → 站点文件不在 nginx 用户有权限的目录。
- `yum` 提示 lock → 另一个窗口正在装，`/run/yum.pid` 有记录，等或杀。
- vim 异常退出后每次提示 → 删掉 `.xxx.swap`。
- 容器里改代码不生效 → 代码是 COPY 进镜像的，需重新 build；要么改成 `-v` 映射。

## 10 关键知识清单

1. Linux = 内核 + GNU 工具；发行版差异在包管理，85% 命令通用。
2. PATH 决定命令能否被找到；用户变量覆盖系统变量。
3. 权限三身份三权限，数字法 r=4/w=2/x=1；chattr +i 可锁文件。
4. 软链接指路径、硬链接共 inode；软链接常用于把软件接入 PATH。
5. systemctl 管服务，ps/top/kill 管进程，dnf 管软件。
6. Docker 解决环境一致性；镜像类、容器对象；`-p` 端口映射、`-v` 数据持久化。
7. 数据库容器必须做目录映射，否则删容器即丢数据。
8. Dockerfile 是镜像的源代码，CMD 可被覆盖、ENTRYPOINT 不会；分层决定构建缓存与体积。
9. Compose 是单机编排，一个服务一个容器，服务间用服务名通信，一条 `up` 拉起整套系统。
10. 交付思维：开发产出 Dockerfile/compose，运维只负责 clone + up。
