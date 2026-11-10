# GitHub 项目二次开发与 Mealie 本地部署

> 来源：python 山顶会三期 day08（`day08/day08/day01.md`，Github 项目二次开发）
> 定位：从零接手一个陌生开源项目的完整路径——工具链 → 拿代码 → 看结构 → 备环境 → 起服务 → 验证 → 排障

## 总览

这节课不讲具体业务，讲的是"进入一个别人写好的项目"这件事本身。主线只有一个：以开源食谱项目 **Mealie** 为目标，用 Git 拿到源码，用 uv/Docker 把环境跑起来，用 Chrome 或 AI 工具读懂结构，最后用页面、容器、日志三项把"跑成功"这件事验证掉。后面 day09–day12 的源码分析、字段扩展、AI 功能、生产部署，全部建立在这条链路之上。

## 1. 二次开发的七步路径

1. 准备开发工具（编辑器 + AI 助手）
2. 获取项目源码
3. 了解项目结构
4. 准备运行环境
5. 本地部署并启动项目
6. 成功访问项目
7. 检查项目是否运行正常

顺序不能反：**先让项目跑起来，再谈改代码**。跑不起来的项目，任何"分析"都是纸上看花。

## 2. 开发工具与 AI 助手

编辑器分两类：传统编辑器（PyCharm、VS Code）和 AI 编辑器（VS Code + Codex / Claude Code / 通义灵码、Cursor、Trae、Antigravity 等）。

Codex 的定位要摆正：**它不是替你思考，而是帮你更快地读项目、定位问题、整理思路、生成草稿**。读开源项目真正耗时的从来不是敲代码，而是：

- 不知道从哪个文件看起
- 不知道某个配置文件有什么作用
- 不知道一个功能对应哪条调用链
- 遇到报错不知道先查哪里

这几类问题最适合丢给 AI 先分析。课程给的使用边界很实用：解释目录结构、解释关键配置文件、分析启动流程、协助定位功能代码、协助排查错误、生成代码草稿。但**不要让 AI 从零写爬虫、编译这类东西**，更好的姿势是给它一份样本或参考案例，让它在样本基础上纠错、完善。

自定义指令（system prompt）里值得借鉴的几条：

- 中文回复，代码标识符/命令/日志保持原样
- 先验证再判断：可疑信息必须先用工具查证，禁止"光质疑不验证"
- 事实确认：不把猜测当事实陈述
- 优先编辑现有文件而不是新建文件
- 任务性质确认：写计划/文档时不动源代码

提问方式也决定质量：问"这个目录负责什么""这个配置文件哪些字段最关键""登录请求从哪个路由进、经过哪些层"，比"帮我看看这个项目"有效得多。

## 3. Git：先看状态，再动手

核心概念五个：仓库（repository）、工作区（working tree）、暂存区（staging area）、提交（commit）、分支（branch）。流程可以压成一行：

```text
修改文件 -> git add -> git commit -> 形成一次历史记录
```

首次安装后的配置：

```powershell
git config --global user.name "你的姓名或英文名"
git config --global user.email "你的邮箱"
git config --global core.autocrlf true   # Windows 下减少换行符差异
```

常用命令与用途：

| 命令 | 用途 |
| --- | --- |
| `git clone <地址>` | 拉取远程仓库 |
| `git status` | 看当前工作区状态（最高频） |
| `git log --oneline -n 5` | 看最近提交，接手项目时先看它在改什么 |
| `git branch` | 确认自己在哪个分支 |
| `git diff` | 提交前确认"我到底改了什么" |
| `git pull` | 同步远程（不是万能修复命令） |
| `git checkout -b feature/demo` | 新建并切到功能分支 |
| `git add .` / `git commit -m "..."` | 入暂存区 / 写历史记录 |

选项目时看基本条件：开源平台项目 stars 越高越稳。拿 Mealie 源码：

```powershell
git clone --depth 1 https://github.com/mealie-recipes/mealie.git
cd mealie
git status
git log --oneline -n 5
```

`--depth 1` 是浅克隆，只拉最近一次提交，体积小、速度快，适合首次获取大项目。

三个高频场景：

- **第一次接手项目**：clone → cd → status → log → branch
- **准备开始开发**：status → pull → checkout -b feature/xxx（先看状态再同步，最后开分支）
- **提交前自查**：status → diff → add → commit → pull → push（最容易被忽略的是 diff）

四条经验：先 `git status` 再决定操作；`git pull` 在脏工作区会引入冲突；提交信息要让人看懂（`update` 等于没写，`feat: add recipe difficulty field` 才有信息量）；不要在主分支长期堆改动。

## 4. uv：Python 环境与依赖的统一入口

`uv` 管三件事：Python 版本、虚拟环境、依赖。常用命令按用途分组：

| 命令 | 用途 |
| --- | --- |
| `uv --version` | 确认工具安装 |
| `uv python list` / `uv python install 3.12` | 看/装 Python 版本 |
| `uv venv` | 创建虚拟环境 |
| `uv sync` | 按项目配置同步依赖 |
| `uv sync --group dev` / `--extra pgsql` | 装开发依赖 / 可选依赖 |
| `uv run python xxx.py` | 在项目环境里执行 |
| `uv add` / `uv remove` / `uv lock` / `uv tree` | 增删依赖、锁版本、看依赖树 |

拿到一个新 Python 项目的检查顺序：

```powershell
uv --version
uv venv
uv sync
uv run python -V
uv run pytest
```

五步分别在确认：工具有没有装好、环境有没有建出来、依赖全不全、命令跑在哪个解释器里、环境能否跑测试。之后遇到"依赖装了却不能用"就沿这条线回头查。

Mealie 本地开发示例：

```powershell
uv venv
uv sync --extra pgsql --group dev
uv run python mealie/app.py
uv run pytest
```

三个误区：一是 `pip`、`conda`、`uv` 混着用，依赖装到不同位置；二是一见 `ModuleNotFoundError` 就改代码，其实应先查环境；三是没理解 `uv run python app.py` 和 `python app.py` 的区别——后者可能是系统全局解释器。

## 5. Docker：把运行环境打包

五个概念必须分清：

- **镜像**：运行环境的打包结果（基础环境 + 依赖 + 代码 + 启动命令），可复用模板
- **容器**：镜像跑起来的实例
- **Compose**：一组服务的启动清单（Web、数据库、Redis、定时任务）
- **端口映射**：容器内端口与宿主端口的对应关系
- **数据卷**：持久化数据，决定"容器重启后数据丢不丢"

基础检查：

```powershell
docker --version
docker compose version
docker info     # 这条报错通常说明 Docker Desktop 还没真正启动
```

常用命令：

```powershell
docker compose up -d --build   # 构建并后台启动
docker compose ps              # 看服务状态（页面打不开先看这个）
docker compose logs --tail 50  # 最近 50 行日志
docker compose logs -f         # 持续跟踪
docker compose exec <服务名> sh # 进容器
docker compose restart / down  # 重启 / 停止并移除容器
```

看一个 Docker 项目，先看 `docker-compose.yml`，重点回答五个问题：定义了哪些服务、哪些要本地构建、暴露了哪些端口、挂了哪些数据卷、设了哪些环境变量。

页面打不开时的排查顺序是 `ps` → `logs`，先分清问题类型：容器没起来、容器起来但应用报错、应用正常但端口映射错、应用正常但地址写错。日志不够再进容器查目录、挂载、环境变量。

经验三条：先看日志别靠猜；不要随意清理数据卷（里面可能是业务数据）；容器在运行 ≠ 应用可用，还要做最小功能验证。

## 6. 辅助工具：DeepWiki 与 NotebookLM

- **DeepWiki**：给仓库生成可对话的项目文档，适合沉淀"项目是干什么的、模块怎么分、启动流程是什么"，推荐按固定格式记录（项目定位、目录职责、启动链路、关键配置）。
- **NotebookLM**：把课件、文档、源码说明导入后集中问答，适合在写笔记前做交叉验证，注意资料来源要标清。

工具使用顺序：先 AI 助手读结构 → 再用 Git/uv/Docker 把项目跑起来 → 用 DeepWiki/NotebookLM 沉淀理解 → 最后才动代码。

## 7. Mealie 项目分析

Mealie 是开源家庭食谱管理系统：菜谱管理、菜谱导入、餐食计划、购物清单、Cookbook 分类、第三方 API。技术上是一个典型前后端分离项目：

- 后端：FastAPI + SQLAlchemy + Alembic
- 前端：Vue + Nuxt
- 部署：Docker Compose

顶层目录与职责：

| 目录 | 说明 |
| --- | --- |
| `mealie/` | 后端主应用代码 |
| `frontend/` | 前端页面代码（Nuxt 项目） |
| `docker/` | Docker 启动与部署文件 |
| `docs/` | 官方文档 |
| `tests/` | 测试代码 |

后端关键目录：

| 路径 | 作用 |
| --- | --- |
| `mealie/core/` | 配置、日志、安全等基础能力 |
| `mealie/routes/` | API 路由入口 |
| `mealie/services/` | 业务服务层 |
| `mealie/repos/` | 数据访问层 |
| `mealie/schema/` | Pydantic 数据结构 |
| `mealie/db/` | 数据库模型、迁移、初始化 |

`docker/` 下重点文件：`docker-compose.yml`、`docker-compose.dev.yml`、`Dockerfile`、`entry.sh`、`healthcheck.sh`——它们决定怎么构建、怎么启动、怎么健康检查。

## 8. 运行方式选择

| 方式 | 适合场景 | 额外依赖 |
| --- | --- | --- |
| Docker Compose（推荐） | 首次运行、快速复现 | 只需 Git + Docker |
| 本地开发模式 | 断点调试、改前端、开发新功能 | Python 3.12、uv、Node.js 22、yarn、task |

第一阶段优先用 Docker 把项目跑通，再切本地开发模式。

## 9. 四个关键配置文件

启动前先看这四个文件，能省掉大量试错：

| 文件 | 看什么 |
| --- | --- |
| `README.md` | 项目定位与官方说明 |
| `pyproject.toml` | Python 依赖、后端核心框架、打包与脚本配置 |
| `frontend/package.json` | 前端技术栈与启动命令 |
| `docker/docker-compose.yml` | 容器怎么起（最重要） |

从 `docker/docker-compose.yml` 能直接读到：宿主端口 `9091` → 容器端口 `9000`、默认数据库 `sqlite`、数据挂载目录 `/app/data/`。

## 10. 启动与验证

```powershell
cd mealie/docker
docker compose up -d --build
docker compose ps
docker compose logs --tail 50
```

首次构建慢是正常的：拉基础镜像、构建前端静态资源、装 Python 依赖、构建运行镜像。

访问 `http://localhost:9091`，默认管理员：`changeme@example.com` / `MyPassword`。

启动成功的最小验证三项：

1. **页面**：登录页能开、默认账号能登、能进主界面
2. **容器**：`docker compose ps` 没有退出或异常状态
3. **日志**：没有明显启动错误、没有数据库初始化失败、没有持续重复报错

## 11. 启动过程里发生了什么

后端两个入口：

- `mealie/main.py`：用 `uvicorn` 启动应用，读取 `API_HOST/API_PORT`，支持日志与 TLS 配置
- `mealie/app.py`：创建 FastAPI 实例、注册中间件、挂载路由、执行生命周期逻辑

启动时还会做数据库初始化：检查连接、执行迁移、初始化默认分组、默认家庭、默认管理员用户。所以"登录失败"不一定是前端问题，很可能和初始化没成功有关。

## 12. 常见问题

| 现象 | 处理 |
| --- | --- |
| `docker compose up` 提示服务不可用 | 启动 Docker Desktop，等 Engine 完全可用再重试 |
| `9091` 端口被占用 | 改 `docker/docker-compose.yml` 为 `9092:9000`，访问 `http://localhost:9092` |
| 首次构建很慢 | 正常现象，只要日志无报错就继续等 |
| 登录失败 | 依次查：地址对不对 → 容器是否正常 → 日志有无初始化报错 → 默认账号是否被改 |

## 关键知识清单

- 二次开发的顺序：先跑起来，再看结构，最后改代码
- AI 助手的正确用法：让它读结构、定位链路、排查错误、按样本改代码，而不是从零造
- Git 三板斧：`status` 看状态、`diff` 看改动、分支隔离改动
- uv 三件事：管 Python 版本、管虚拟环境、管依赖；命令一律 `uv run` 执行
- Docker 排查顺序：`ps` → `logs` → 进容器；数据卷不要随便清
- Compose 文件是理解项目运行方式的入口：服务、端口、卷、环境变量
- Mealie：FastAPI + SQLAlchemy + Alembic + Nuxt，Docker 起在 `9091→9000`
- "跑成功"的判定标准是页面 + 容器 + 日志三项同时正常
