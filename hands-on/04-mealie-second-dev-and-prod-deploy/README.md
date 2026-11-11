# Mealie 二次开发与生产部署实操（day08–day12）

> 来源：python 山顶会三期 day08–day12（GitHub 项目二次开发 → Mealie 源码分析 → Nuxt 字段扩展 → AI 摘要 → 生产部署）
> 定位：把五节课串成一条「读懂开源项目 → 加字段 → 接 AI → 上生产」的完整链路，全部本机真跑，日志随目录提交
> 对应笔记：`notes/08-*` ～ `notes/12-*` 五篇（理解向记录）；本目录是**自己动手实现并验证**的版本
> 上游项目：Mealie v3.15.1（`mealie-next`，FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic / Nuxt 4 + Vue 3 + Vuetify）

## 1. 案例主线

核心目标：给一个成熟的开源食谱管理项目加两个真功能，并按生产标准部署上线。

1. **字段扩展**：给 Recipe 增加 `difficulty`（难度），贯通数据库迁移 → ORM → Schema → 路由 → 前端表单/展示/生成类型
2. **AI 功能**：新增 `POST /api/recipes/{slug}/ai-summary`，调用 LLM 输出结构化摘要（summary / difficulty / estimated_time / highlights / warnings），只读不落库
3. **生产部署**：多阶段 Dockerfile 构建镜像 → Compose 编排 mealie + postgres + nginx 三容器 → 重启不丢数据、pg_dump 可备份

| 阶段 | 对应课次 | 复刻内容 | 关键验证点 |
| --- | --- | --- | --- |
| 本地跑起来 | day08–day10 | clone v3.15.1、uv 装依赖、Alembic 建库、uvicorn 起后端、yarn 起前端 | `/api/app/about` 200；登录拿到 token |
| difficulty 字段 | day11 | ORM `String(32)` → Alembic 迁移 `fc7cdab5b7a2` → Schema → PUT 写库 → 前端 InfoCard/InfoEditor + i18n | 写入 medium 读回 medium；改 hard 读回 hard；迁移版本落库 |
| AI 摘要 | day12 上半 | `OpenAIRecipeSummary` Schema、Prompt 六条边界、Service + 薄 Route、前端 API/卡片组件、生成 TS 类型 | DeepSeek 返回结构化 JSON；不存在的 slug 返回 404；不落库 |
| 生产部署 | day12 下半 | 五阶段 Dockerfile、`/opt/mealie` 目录、`.env.production`、Compose 三容器、nginx 反代 | 三容器 healthy；9925 直连与 8080 反代均 200；重启后数据仍在；pg_dump 成功 |

## 2. 目录结构

```
04-mealie-second-dev-and-prod-deploy/
├── backend/                      # 后端改动后的完整文件（按仓库相对路径）
│   └── mealie/
│       ├── db/models/recipe/recipe.py            # + difficulty 列
│       ├── schema/recipe/recipe.py               # + difficulty 字段
│       ├── schema/openai/recipe_summary.py       # 新增 OpenAIRecipeSummary
│       ├── schema/openai/__init__.py             # 导出新 Schema
│       ├── services/recipe/recipe_ai_summary_service.py   # 新增摘要服务（含 JSON 模式降级）
│       ├── services/openai/prompts/recipes/summarize-recipe.txt  # 新增 Prompt
│       ├── routes/recipe/recipe_crud_routes.py   # + POST /{slug}/ai-summary
│       └── alembic/versions/2026-11-11-10.14.22_fc7cdab5b7a2_add_recipe_difficulty.py
├── frontend/                     # 前端改动后的完整文件（按仓库相对路径）
│   └── frontend/app/
│       ├── components/Domain/Recipe/RecipePage/RecipePage.vue              # 挂载摘要卡片
│       ├── components/Domain/Recipe/RecipePage/RecipePageParts/
│       │   ├── RecipePageAiSummary.vue           # 新增 AI 摘要卡片
│       │   ├── RecipePageInfoCard.vue            # 展示 difficulty
│       │   └── RecipePageInfoEditor.vue          # 编辑 difficulty
│       ├── lang/messages/{en-US,zh-CN}.json      # 难度与摘要文案
│       └── lib/api/
│           ├── types/openai.ts                   # 生成的 OpenAIRecipeSummary 类型
│           ├── types/recipe.ts                   # 生成的 difficulty 字段
│           └── user/recipes/recipe.ts            # generateAiSummary()
├── deploy/
│   ├── Dockerfile                # 五阶段构建（含 pip 镜像与 CRLF 修复）
│   ├── dockerignore              # 构建上下文排除项（放仓库根目录时改名 .dockerignore）
│   ├── gitattributes             # 新增 *.sh text eol=lf
│   ├── entry.sh / healthcheck.sh # 容器入口与健康检查（LF）
│   ├── docker-compose.prod.yml   # mealie + postgres + nginx
│   ├── nginx/conf.d/mealie.conf  # 反代到 http://mealie:9000
│   └── .env.production.example   # 生产环境变量模板（无真实 key）
├── scripts/
│   ├── gen_frontend_types.py     # 类型生成（跳过脚本末尾的 yarn lint）
│   ├── e2e_api.py                # E2E：difficulty + ai-summary（BASE_URL 可切换环境）
│   ├── deploy_up.sh              # 幂等部署到 /opt/mealie 并拉起三容器
│   ├── check_prod_db.sh          # 生产库迁移版本与难度列检查
│   ├── prod_restart_backup.sh    # 重启验证数据不丢 + pg_dump 备份
│   └── check_pypi_mirrors.sh     # PyPI 镜像测速
├── logs/                         # 12 份运行日志（验证证据）
├── mealie-customization.patch    # 相对 v3.15.1 的全部改动（20 个文件，728 行）
└── README.md
```

## 3. 运行环境

| 项 | 版本 / 说明 |
| --- | --- |
| 后端 | Python 3.12（uv 管理）、FastAPI、Pydantic v2、SQLAlchemy 2、Alembic |
| 前端 | Node 24.13.0、Yarn 1.22.22（corepack）、Nuxt 4、Vue 3、Vuetify |
| 数据库 | 开发栈 SQLite；生产栈 PostgreSQL 15 |
| 部署 | WSL2 Ubuntu 24.04.5 LTS + Docker Engine 29.1.3 + Compose v2.40.3 |
| 模型 | DeepSeek `deepseek-chat`（OpenAI 兼容），key 只放 `.env` / `.env.production`，不入库 |
| 加速 | PyPI 用阿里云镜像（`PIP_INDEX_URL` / `UV_INDEX_URL` / `UV_DEFAULT_INDEX`）；npm 用 `registry.npmmirror.com` |

## 4. 复现方式

### 4.1 打补丁

```bash
git clone --depth 1 --branch v3.15.1 https://github.com/mealie-recipes/mealie.git
cd mealie
git apply /path/to/mealie-customization.patch   # 或直接复制 backend/ frontend/ 下的文件
```

### 4.2 本地开发栈

```bash
# 后端（仓库根目录）
uv sync --extra pgsql --group dev
uv run alembic upgrade head          # 迁移到 fc7cdab5b7a2，含 difficulty 列
uv run uvicorn mealie.app:app --port 9000

# 前端（frontend/）
corepack yarn install
corepack yarn dev                    # 访问 http://localhost:3000

# 可选：Schema 改完后重新生成 TS 类型
python scripts/gen_frontend_types.py # 等价 dev/code-generation/main.py types，但跳过末尾 yarn lint
```

### 4.3 生产栈

```bash
# 1. 构建镜像（本机 docker 缺 buildx，走 legacy builder）
DOCKER_BUILDKIT=0 docker build -t mealie:3.15.1-custom -f docker/Dockerfile .

# 2. 准备 /opt/mealie（compose、nginx 配置、数据目录、env）
#    .env.production 至少包含：ALLOW_SIGNUP / PUID / PGID / TZ / BASE_URL /
#    DB_ENGINE=postgres / POSTGRES_{USER,PASSWORD,SERVER,PORT,DB} /
#    OPENAI_BASE_URL / OPENAI_API_KEY / OPENAI_MODEL / OPENAI_REQUEST_TIMEOUT

# 3. 拉起三容器（脚本内部幂等：已存在的 .env.production 不会被重置密码）
bash scripts/deploy_up.sh

# 4. 验收
bash scripts/check_prod_db.sh        # alembic_version=fc7cdab5b7a2，recipes.difficulty 存在
BASE_URL=http://127.0.0.1:8080 python scripts/e2e_api.py   # 走 nginx 全链路
bash scripts/prod_restart_backup.sh  # 重启后数据仍在 + pg_dump 备份
```

## 5. 验证结果（日志见 `logs/`）

| 日志 | 关键证据 |
| --- | --- |
| `02_alembic_upgrade.log` | 迁移 `fc7cdab5b7a2` 执行成功，`recipes.difficulty` 建立 |
| `04_e2e_api.log` | 开发栈 9000 端口：建菜谱 201、difficulty medium→hard 两次读回一致、ai-summary 200、不存在 slug 404 |
| `08_dev_generate_types.log` | 12 个模块类型全部 Saved，`openai.ts` 产出 `OpenAIRecipeSummary` |
| `09_nuxt_prepare.log` / `10_frontend_lint.log` | `.nuxt` 准备完成；ESLint 0 error |
| `11_frontend_build_tail.log` | `Build complete!`（Nuxt 生产构建 115.98s） |
| `12c_docker_build_steps.log` / `12c_docker_rebuild.log` | 修复 CRLF 后重建：52 步、`Successfully tagged mealie:3.15.1-custom`（1.73GB） |
| `13_deploy_up.log` | 三容器 `Up (healthy)`：mealie_app / mealie_postgres / mealie_nginx |
| `14_prod_db_check.log` | 生产库 `alembic_version=fc7cdab5b7a2`、`difficulty character varying YES`、admin 用户存在 |
| `15_prod_e2e.log` | 走 nginx 8080：difficulty 写入/改值/读回正确；DeepSeek 返回中文摘要 + difficulty/estimated_time/highlights/warnings；404 正确 |
| `16_prod_restart_backup.log` | `docker compose restart mealie` 后 `fan-qie-chao-dan-e2e-hard|hard` 仍在；`pg_dump` 备份 135K 成功 |

生产栈实测返回（摘自 `15_prod_e2e.log`）：

```json
{
  "summary": "这是一道15分钟就能上桌的家常番茄炒蛋，甜咸口，适合赶时间的晚餐。……",
  "difficulty": "easy",
  "estimated_time": "准备约5分钟，烹饪约10分钟，总计约15分钟。",
  "highlights": ["15分钟内完成，食材仅三样，适合工作日晚餐。", "..."],
  "warnings": ["食材只列出名称和大致数量，没有精确克数，调味比例需凭经验把握。", "..."]
}
```

## 6. 踩坑记录

1. **`pydantic2ts` 依赖外部 node 命令 `json2ts`**：类型生成器最终执行 `os.system("json2ts -i schema.json -o out.ts")`，WSL 里没有 node 直接失败。装 `nodejs+npm` 后 `npm i -g json-schema-to-typescript --registry=https://registry.npmmirror.com` 解决。
2. **类型生成脚本末尾会跑 `yarn lint --fix`**：`dev/code-generation/gen_ts_types.py` 的 `main()` 最后一步 `subprocess.run(["yarn","lint","--fix"], cwd="frontend")`，在 WSL 跑会找不到 yarn 且没必要。用 `gen_frontend_types.py` monkey-patch `subprocess.run` 跳过，lint 交给 Windows 侧统一跑。
3. **重新生成的类型文件混入版本噪音**：除 `recipe.ts`/`openai.ts` 外的 10 个类型文件被 pydantic2ts 加上了 `[k: string]: unknown` 之类无关改动，全部 `git checkout --` 还原，保持最小 diff。
4. **ESLint 报 `.nuxt/eslint.config.mjs` 不存在**：先 `corepack yarn nuxt prepare` 生成 `.nuxt` 再 lint。
5. **DeepSeek 不支持 `json_schema` 结构化输出**：`client.chat.completions.parse(response_format=schema)` 返回 400 `This response_format type is unavailable now`。改为 `{"type":"json_object"}` + `model_validate_json`，并剥掉可能的 ` ```json ` 围栏；Service 里做了自动降级（先试结构化输出，400 才降级）。
6. **Docker 29.1.3（Ubuntu 包）缺 buildx**：`DOCKER_BUILDKIT=1` 报 `buildx component is missing`，统一改用 `DOCKER_BUILDKIT=0`（legacy builder 有 deprecated 警告但可用）。
7. **PyPI 直连极慢**：容器内 `pip install uv` 卡 21 分钟只下到 12.3/17.2MB。测速发现 pypi.org 20s 超时、阿里云 0.22s。Dockerfile 的 python-base 阶段加 `PIP_INDEX_URL` / `UV_INDEX_URL` / `UV_DEFAULT_INDEX` 三个 ARG/ENV 后重建 25 分钟成功。
8. **CRLF shebang 让容器无限重启**：Windows 检出的 `entry.sh` 是 CRLF，`#!/bin/bash\r` 导致 `exec /app/run.sh: no such file or directory`（exit 255 循环）。三重修复：`sed -i 's/\r$//'` 转 LF、`.gitattributes` 加 `*.sh text eol=lf`、Dockerfile 里 COPY 后再 `sed` 兜底。
9. **部署脚本每次重置数据库密码**：第一次 `up` 时随机生成 `POSTGRES_PASSWORD`，重跑脚本又生成新密码，但 postgres 卷已用旧密码初始化 → 认证失败。改为幂等：`.env.production` 已存在则保留，缺失 key 才补。
10. **WSL 的 git 与 Windows git 行尾配置不同**：用 WSL git 生成 patch 时 `core.autocrlf` 默认 false，把 CRLF 工作区文件当成整文件重写（68MB patch）；加 `-c core.autocrlf=true` 后回到 32K/728 行。
11. **PowerShell 会展开 `$` 和吃掉引号**：`psql -c "\d recipes"`、`$POSTGRES_USER` 这类命令在 `wsl bash -c "..."` 里必坏。所有多行/含变量的操作一律写成 `.sh` 文件再执行（`sed -i 's/\r$//'` 先转 LF）。

## 7. 与课件的取舍

- **模型**：课件用 OpenAI/DeepSeek 混讲，这里统一 DeepSeek `deepseek-chat`，并针对其不支持的 `json_schema` 做了降级兼容（课件只讲理想路径）。
- **持久化**：AI 摘要按课件设计**只读不落库**，每次点击重新生成；如要缓存可自行加表。
- **数据库**：开发栈用 SQLite（跑得快），生产栈用 PostgreSQL 15（compose 里的真实路径），迁移在两种库上都验证过。
- **部署**：课件用四段 Dockerfile 的写法，本仓库为上游五段结构，只在必要处加了三处改动（pip 镜像、两处 LF 修复），其余保持上游原样。
- **HTTPS**：课件挂了完整 letsencrypt 目录，这里只验证 80 端口反代链路（本机无域名/证书），nginx 配置留了扩展位。
- **密钥**：所有脚本只从 `.env` 读取 key，日志与提交内容不含任何真实 key。
