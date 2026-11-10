# Mealie 项目结构与 uv 本地开发环境

> 来源：python 山顶会三期 day09（`day09/day01.md` 修订版 + `day09/答疑.md`）
> 定位：在 day08 已能把项目跑起来的基础上，把目录结构读细，并补齐 uv + yarn 的本地开发模式

## 总览

day09 的课件是 day08 同主题的修订版，主线没变（GitHub 项目二次开发 → 跑起 Mealie），增量集中在三块：**带注释的完整目录树**、**uv 管理本地依赖**、**前端 yarn 启动**，另外答疑里补充了 AI 工具选型的问题。所以这份笔记不再重复 Git/Docker 的基础操作，只记"结构怎么读、本地怎么开发"。

## 1. 读一个陌生项目的文件顺序

课件给出的源码阅读顺序，本质是"从能跑到能改"：

```text
README.md
-> pyproject.toml
-> Taskfile.yml
-> mealie/main.py
-> mealie/app.py
-> mealie/routes/__init__.py
-> mealie/routes/recipe/recipe_crud_routes.py
-> mealie/routes/recipe/_base.py
-> mealie/services/recipe/recipe_service.py
-> mealie/repos/repository_recipes.py
-> mealie/db/models/recipe/recipe.py
-> mealie/schema/recipe/recipe.py
-> frontend/pages/g/[groupSlug]/r/[slug]/index.vue
```

好处：先知道项目怎么跑，再知道接口怎么进，再知道业务怎么处理，最后知道数据怎么存、页面怎么展示。

## 2. 项目结构全景

顶层目录：

| 目录/文件 | 职责 |
| --- | --- |
| `.github/` | Issue/Discussion 模板、GitHub Actions 工作流 |
| `dev/code-generation/` | 代码与资源生成脚本（本地化、类型生成） |
| `docker/` | `docker-compose.yml`、`docker-compose.dev.yml`、Dockerfile、entry.sh |
| `docs/` | MkDocs 文档站源码 |
| `frontend/` | Nuxt 3 + Vue 3 + Vite 前端 |
| `mealie/` | FastAPI 后端主包 |
| `tests/` | 测试代码 |

后端 `mealie/` 关键子目录：

| 路径 | 职责 |
| --- | --- |
| `app.py` / `main.py` | 开发态入口（创建 FastAPI 应用）/ 生产态 CLI 入口（uvicorn） |
| `core/config.py` | 读 `.env`、判断运行环境、构造全局配置 |
| `core/settings/settings.py` | 主配置模型 `AppSettings`（数据库、SMTP、OIDC、OpenAI） |
| `core/settings/db_providers.py` | SQLite / PostgreSQL 连接信息构造 |
| `db/init_db.py` | 启动时数据库初始化、迁移执行、默认数据创建 |
| `db/models/` | ORM 模型定义 |
| `routes/__init__.py` | 聚合所有子路由，统一挂到 `/api` |
| `routes/recipe/` 等 | 按业务域拆分的路由目录 |
| `repos/` | Repository 层，封装数据读写 |
| `schema/` | Pydantic 请求体/响应体结构 |
| `services/` | 业务服务层，连接 routes 与 repos |
| `lang/`、`middleware/` | 国际化资源、请求语言上下文中间件 |

前端 `frontend/` 关键子目录：

| 路径 | 职责 |
| --- | --- |
| `pages/` | 基于文件系统生成路由（Nuxt 约定） |
| `components/Domain/` | 业务领域组件（Recipe、Cookbook、ShoppingList、User） |
| `components/global/`、`components/Layout/` | 通用组件、布局组件 |
| `composables/` | 组合式函数：API 调用、表单、状态、页面逻辑 |
| `layouts/` | 布局模板：default / admin / basic / blank / error |
| `middleware/` | 路由中间件：`admin-only.ts`、`group-only.ts`、PWA 全局跳转 |
| `lib/api/` | 按 admin/public/user 分类的 API 客户端封装 |
| `lang/messages/` | 多语言 JSON 文案（i18n） |
| `nuxt.config.ts` | 前端配置中心 |
| `package.json` / `yarn.lock` | 依赖与脚本命令、依赖版本锁定 |

读结构的技巧：**先看职责表，再带着一个具体功能往回找文件**。比如"菜谱详情页"就落在 `pages/g/[groupSlug]/r/[slug]/index.vue` + `components/Domain/Recipe/`，顺着这一条链就能摸到后端接口。

## 3. uv 管理本地依赖

Mealie 的 Python 依赖由 uv 管理。安装后在新终端执行 `uv`，有输出即安装成功。

常用命令（本地开发够用的一组）：

```powershell
uv --version
uv venv
uv sync
uv run python -V
uv run python mealie/app.py
uv run pytest
```

Mealie 的具体用法：

```powershell
uv venv
uv sync --extra pgsql --group dev
uv run python mealie/app.py
uv run pytest
```

- `--extra pgsql`：额外同步 PostgreSQL 相关依赖
- `--group dev`：同步开发依赖（测试、格式化、调试工具）
- `uv run ...`：确保命令执行在项目自己的环境里

三条经验：项目定了 uv 就别混用 pip/conda；报 `ModuleNotFoundError` 先查环境再改代码；`uv run python app.py` 与 `python app.py` 可能不是同一个解释器。

## 4. 前端本地启动

后端提供 API，前端要单独起。先保证本机有 Node.js，再通过 npm 安装 yarn（类似 pip/uv 的包管理器），然后：

```bash
yarn          # 安装依赖
yarn dev      # 启动开发服务器
```

配合后端 `uv run python mealie/app.py`，就是完整的本地开发模式；改前端页面不需要重建 Docker 镜像。

## 5. Docker 方式仍然是最小验证首选

本地开发模式依赖太多（Python 3.12 + uv + Node 22 + yarn + task），首次跑通仍建议 Docker：

```powershell
cd docker
docker compose up -d --build
docker compose ps
```

端口关系：宿主机 `9091` → 容器 `9000`，默认账号 `changeme@example.com` / `MyPassword`。

## 6. 启动链路里容易忽略的一段

启动不只是"Web 服务起来了"，`app.py` 的生命周期里还会：

1. 检查数据库连接
2. 执行数据库迁移
3. 初始化默认分组、默认家庭、默认管理员用户

所以页面能打开但登录失败时，优先怀疑初始化没跑完，而不是账号密码写错。判断依据在日志里：`database initialization` 之后的报错最关键。

## 7. 答疑补充

- **Codex 与 Claude Code 的差别**：Claude Code 是 Anthropic 的产品，对应 Claude Opus 系列；Codex 是 OpenAI 的产品，对应 GPT 系列，普通账号也能用较新的模型。两者定位类似，都是"读项目 + 改代码"的 AI 助手，选一个顺手的即可。
- **临时邮箱注册失败**：多半是邮箱域名被封，换一个域名，或直接用微软/雅虎这类大厂邮箱。

## 关键知识清单

- 读项目的顺序：README → 依赖配置 → 任务入口 → 启动入口 → 路由 → 业务 → 模型 → 前端页面
- 结构记忆法：`routes` 进、`services` 处理、`repos` 取数、`db/models` 存、`schema` 收返
- 前端按 Nuxt 约定组织：`pages` 出路由，`components/Domain` 装业务组件，`composables` 收逻辑
- uv 三件套：`uv venv` 建环境、`uv sync` 装依赖、`uv run` 跑命令
- 本地开发 = 后端 `uv run python mealie/app.py` + 前端 `yarn dev`
- 登录失败先查数据库初始化，不要只盯前端
- Docker 仍是最小验证的首选路径，本地模式用于调试和开发
