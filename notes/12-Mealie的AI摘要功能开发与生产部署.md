# Mealie 的 AI 摘要功能开发与生产部署

> 来源：python 山顶会三期 day12（`day12-二次开发-AI功能二次开发与项目部署/笔记.zip` 内 `day04-Mealie 项目二次开发（AI 功能）.md` + `day05-Mealie 项目部署.md`）
> 定位：上半场在已有开源项目里加一条 AI 能力链路，下半场把这套代码部署成一台能对外服务的生产环境

## 总览

day12 是前面所有课的收口：day10 读懂了源码分层，day11 加了一个普通字段，这次加的是"调大模型"的接口；然后把这套改过的项目从本地 Docker 搬到云服务器，配上 PostgreSQL、Nginx、HTTPS、备份与回滚。两件事共享同一个前提——**先看项目已经有什么，再决定自己写什么**。

---

# 上半场：AI 摘要功能

## 1. 做 AI 功能前先摸清现状

课件第一句话就是"不要直接写代码"。Mealie 不是空项目，里面已有大量 OpenAI 相关实现，不看就动手，很容易写出一套重复且风格不一致的代码。要读的文件分四组：

| 组别 | 文件 |
| --- | --- |
| 依赖与任务 | `pyproject.toml`、`Taskfile.yml` |
| 配置 | `mealie/core/settings/settings.py` |
| 现有 AI 实现 | `mealie/services/openai/openai.py`、`mealie/services/openai/prompts/`、`mealie/schema/openai/` |
| 业务与前端 | `mealie/services/recipe/recipe_service.py`、`routes/recipe/recipe_crud_routes.py`、`frontend/app/lib/api/user/recipes/recipe.ts`、`RecipePage/` 组件目录、`types/openai.ts` |

两个容易踩的坑：

- 项目用 uv 管依赖，命令统一 `uv run ...`，不要裸 `pip install` / `pytest`
- 前端 `types/recipe.ts`、`types/openai.ts` 是 pydantic2ts **自动生成**的，顶部写着"Do not modify it by hand"。正确顺序是改后端 Schema → 跑 `task dev:generate` → 让前端类型自动更新

## 2. 项目已有的三块 AI 基础设施

### 2.1 开关：`OPENAI_ENABLED`

`settings.py` 里已有一组 OpenAI 配置：`OPENAI_BASE_URL`、`OPENAI_API_KEY`（脱敏类型）、`OPENAI_MODEL`（默认 gpt-4o）、`OPENAI_AUDIO_MODEL`、`OPENAI_CUSTOM_HEADERS/PARAMS`、`OPENAI_REQUEST_TIMEOUT`（默认 300）、`OPENAI_CUSTOM_PROMPT_DIR` 等，并提供 `OPENAI_FEATURE` 与 `OPENAI_ENABLED` 两个判断属性。

核心规则：**API Key 和 Model 都在，才算可用**。所以业务代码里不要自己读 `os.environ`，统一用 `settings.OPENAI_ENABLED`。

本地调试时在 `mealie/.env` 里配三项就能开：`OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL`。

### 2.2 服务：`OpenAIService`

`mealie/services/openai/openai.py` 已经把客户端封装好了，四个要点：

| 能力 | 用法 | 说明 |
| --- | --- | --- |
| 客户端 | `self.get_client()` | 内部是 `AsyncOpenAI(base_url, api_key, timeout, headers, params)`，不要自己 new |
| 读 Prompt | `get_prompt("recipes.summarize-recipe")` | **点号路径**，对应 `prompts/recipes/summarize-recipe.txt` |
| 注入数据 | `OpenAIDataInjection(description, value)` | 自动拼到 Prompt 末尾，格式 `### 描述 --- 内容`，比自己拼长字符串清晰 |
| 结构化返回 | `get_response(prompt, msg, response_schema=Xxx)` | 让模型按 Pydantic Schema 输出，不是自由文本 |

### 2.3 结构化基类与 Prompt 目录

- 结构化基类 `OpenAIBase` 在 `mealie/schema/openai/_base.py`，核心是 `parse_openai_response()`：先预处理响应再解析。**新写的返回 Schema 必须继承它**，不能直接继承 `BaseModel`
- Prompt 按业务目录组织：`prompts/general/`、`prompts/recipes/`（已有 parse-recipe-image、parse-recipe-video、scrape-recipe 等）。新功能属于 Recipe 域，就放 `prompts/recipes/`，**不要硬编码进 Python 字符串**

### 2.4 三个可参考的现成案例

1. 图片生成食谱：`recipe_service.py` 的 `OpenAIRecipeService.build_recipe_from_images`，链路 Route → RecipeService → OpenAIRecipeService → get_prompt → get_response → OpenAIRecipe → Recipe
2. URL 抓取失败兜底：`scraper_strategies.py` 的 `RecipeScraperOpenAI`
3. 后台调试页：`routes/admin/admin_debug.py` + `frontend/app/pages/admin/debug/openai.vue`

这三个案例给出一条固定套路：**Route 管收返、Service 管业务、Prompt 放文件、返回用 Schema 约束、前端走 API 封装**。

## 3. 功能设计

需求：打开某个 Recipe 详情页，点按钮生成 AI 摘要。

第一版**不落库**，即时生成即时展示。理由：不加字段、开发量小；不引入缓存/历史版本/覆盖旧摘要这些复杂问题；先跑通链路，后续要持久化再补。

接口设计：

```text
POST /api/recipes/{slug}/ai-summary
参数：slug（Recipe 的 slug 或 id）
```

返回结构化 JSON 而不是一段文本，五个字段各有前端用途：

| 字段 | 前端展示 |
| --- | --- |
| `summary` | 正文 |
| `difficulty` | 标签 |
| `estimated_time` | 信息卡片 |
| `highlights` | 列表 |
| `warnings` | 注意事项块 |

## 4. 输入数据要裁剪

最常见的错误是把整条 `Recipe` 丢给模型。Recipe 详情里包含 `id`、`user_id`、`household_id`、`group_id`、`image`、`settings`、`assets`、`comments`、`extras`、`created_at` 等字段，对摘要没用，还增加 token 成本与泄漏风险。

只发这些：`name`、`description`、`difficulty`、`recipe_yield`、`total_time`、`prep_time`、`perform_time`、`recipe_category`、`tags`、`tools`、`recipe_ingredient`、`recipe_instructions`、`notes`。

注意 `difficulty` 是 day11 加的字段，这里作为**参考输入**——模型可以基于食材和步骤重新给出难度判断。

## 5. 四层新增

### 5.1 返回 Schema：`mealie/schema/openai/recipe_summary.py`

`OpenAIRecipeSummary(OpenAIBase)`，五个字段全部带 `description`（这些描述会参与结构化输出约束）：

- `summary: str | None`
- `difficulty: str | None`（描述里限定 easy / medium / hard；第一版用字符串不上枚举，降低兼容成本）
- `estimated_time: str | None`
- `highlights: list[str]`（`default_factory=list`）
- `warnings: list[str]`（`default_factory=list`）

同时在 `mealie/schema/openai/__init__.py` 的导出里补上它（这个文件由 `gen_schema_exports.py` 自动生成，跑 `task dev:generate` 后确认自动出现）。

### 5.2 Prompt：`prompts/recipes/summarize-recipe.txt`

不用写复杂，重点是**约束边界**六条：

1. 不要编造食材
2. 不要输出数据库 ID 或实现细节
3. 输出面向家庭烹饪者，不是面向开发者
4. 难度限定在 easy / medium / hard
5. 尽量跟随食谱原语言
6. 只返回符合 Schema 的内容

### 5.3 Service：`mealie/services/recipe/recipe_ai_summary_service.py`

单独开文件，不要塞进 CRUD 路由。`RecipeAISummaryService(BaseService)` 两个方法：

- `_serialize_recipe(recipe)`：**主动挑字段**（白名单），不是 `model_dump()` 整条丢出去。好处是控 token、不发无关字段、不发内部 ID、Prompt 输入稳定、以后加字段好审查
- `summarize(recipe)`：`OpenAIService()` → 取 prompt 并注入 Recipe JSON → `get_response(..., response_schema=OpenAIRecipeSummary)` → 空结果抛 `ValueError`

### 5.4 Route：`recipe_crud_routes.py` 里加一个薄接口

在 `RecipeController` 中加 `POST /{slug}/ai-summary`，四步：

1. `if not self.settings.OPENAI_ENABLED` → 抛 400（`ErrorResponse.respond("OpenAI is not enabled")`）
2. `self.service.get_one(slug)` 复用现有查询（含权限上下文）
3. 调 `RecipeAISummaryService().summarize(recipe)`
4. `except Exception as e: self.handle_exceptions(e)`

Route 只做接收、判断开关、调 Service、返回，**不写 Prompt、不直接调 OpenAI、不做字段整理**。

## 6. 前端三处

### 6.1 API 封装

文件 `frontend/app/lib/api/user/recipes/recipe.ts`：

1. `routes` 里加 `recipesAiSummary: (slug) => \`${prefix}/recipes/${slug}/ai-summary\``
2. `types/openai.ts` 里加 `OpenAIRecipeSummary` 接口（summary / difficulty / estimated_time? / highlights? / warnings?）
3. `RecipeAPI` 类末尾加 `generateAiSummary(slug)`，内部 `this.requests.post<OpenAIRecipeSummary>(...)`

### 6.2 展示组件

新增 `RecipePageParts/RecipePageAiSummary.vue`：

- `BaseButton` 触发，带 `loading` 状态
- 出错用 `v-alert` 展示，不白屏
- 成功后渲染 summary 正文、difficulty 与 estimated_time 两个 chip、highlights / warnings 两组列表
- 组合式函数取 api：`useUserApi()`，文案走 `$t('recipe.xxx')`

挂载位置：`RecipePage.vue` 里放在 `RecipePageScale` 之后，条件 `v-if="!isEditForm && !isCookMode"`——不影响编辑表单和烹饪模式。第一版不建议塞进 `RecipePageInfoCard.vue`，否则信息卡片过重。

### 6.3 国际化

`frontend/app/lang/messages/en-US.json` 与 `zh-CN.json` 的 `recipe` 节点里补 `ai-summary`、`generate-ai-summary`、`highlights`、`warnings` 四个 key。注意是**在已有节点里补 key**，不是整段覆盖。

## 7. 验证与检查

接口验证：`http://localhost:9000/docs` 找到 `POST /api/recipes/{slug}/ai-summary`，或 curl 带 token 调；本地登录靠 cookie 时直接点页面按钮更省事。正常返回形如：

```json
{
  "summary": "适合家庭聚餐的甜点，步骤清晰。",
  "difficulty": "medium",
  "estimated_time": "45-60 minutes",
  "highlights": ["适合提前准备", "食材常见"],
  "warnings": ["注意烘烤时间"]
}
```

代码检查：后端 `task py:lint`、`task py:mypy`、`task py:test -- tests/unit_tests`；前端 `task ui:lint`、`task ui:test`。

最低五项手动验证：

1. 没配 OpenAI 时，接口给出明确失败
2. 配好之后点按钮能返回摘要
3. 返回为空时前端不白屏
4. Recipe 不存在时仍走原有 404 逻辑
5. 生成摘要不影响原 Recipe 数据

## 8. 五个"为什么"

| 问题 | 答案 |
| --- | --- |
| 为什么不把摘要存库 | 要回答存哪、覆盖还是留历史、Recipe 改了摘要是否失效、多语言存几份、不同模型差异、缓存成本——第一版不适合全做 |
| 为什么不在前端直接调 OpenAI | Key 不能进浏览器；前端调无法复用后端权限与日志；后端已有配置/Prompt/Schema 管理 |
| 为什么结构化返回 | 纯文本难扩展；结构化才能把难度做成颜色标签、注意事项做成警告块 |
| 为什么单独写 Service | Route 只管 HTTP；数据筛选、Prompt 读取、模型调用、解析、异常都是业务逻辑 |
| 为什么不全量发 Recipe | 无关字段增成本、有隐私风险，白名单更可控 |

## 9. 十五步顺序（照做即可）

1. 读 `openai.py` 确认能力
2. 读 `schema/openai/_base.py` 确认结构化返回方式
3. 读 `recipe_service.py` 里的 `OpenAIRecipeService` 参考写法
4. 新增 `schema/openai/recipe_summary.py`
5. 新增 `prompts/recipes/summarize-recipe.txt`
6. 新增 `services/recipe/recipe_ai_summary_service.py`
7. 改 `recipe_crud_routes.py` 加接口
8. 跑 `task dev:generate` 同步后端导出与前端类型
9. 确认 `schema/openai/__init__.py` 出现 `OpenAIRecipeSummary`
10. 改 `lib/api/user/recipes/recipe.ts` 加方法
11. 新增前端展示组件
12. 详情页引入组件
13. 补中英文 i18n
14. 起前后端验证
15. 跑 lint / 类型检查 / 测试

---

# 下半场：生产部署

## 10. 部署前先看项目给了什么

不要急着 `docker compose up`。先读这份文件清单，它们能回答"镜像怎么建、容器启动跑什么、端口多少、数据在哪、健康检查打哪个接口、数据库怎么配、环境变量从哪读"：

```text
docker/Dockerfile
docker/docker-compose.yml
docker/docker-compose.dev.yml
docker/.env.postgres.example
docker/entry.sh
docker/healthcheck.sh
Taskfile.yml
pyproject.toml
mealie/app.py
mealie/core/settings/settings.py
mealie/core/settings/db_providers.py
```

## 11. 技术栈与端口

- 后端：Python >=3.12,<3.13 + FastAPI + Pydantic + SQLAlchemy + Alembic + Uvicorn + openai，包名 `mealie` 版本 `3.15.1`
- 前端：Nuxt 4 + Vue + Vuetify + TypeScript + Vitest + Yarn
- 前端**不是独立 Node 服务**：Dockerfile 里 `yarn generate` 出静态文件，复制进 Python 包（`COPY --from=frontend-builder /frontend/dist ./mealie/frontend`），生产模式由 FastAPI 挂静态站点（`app.py` 里 `if settings.PRODUCTION and not settings.TESTING: spa.mount_spa(app)`）
- 容器内端口 `APP_PORT=9000`，健康检查脚本默认 `${API_PORT:-9000}`

所以对外映射 `9091:9000` 时，用户实际访问的是宿主机 9091，Nginx 转发到容器内 9000。

## 12. 多阶段 Dockerfile 四段

| 阶段 | 做什么 |
| --- | --- |
| `frontend-builder`（node:24） | `yarn install` → `yarn generate` → 产出 `frontend/dist` |
| `backend-builder` | 复制后端代码 + 前端产物 → `uv build --out-dir dist` 打出 Python 包 |
| 依赖安装 | `python3 -m venv --upgrade-deps $VENV_PATH` 后安装生产依赖 |
| `production` | `PRODUCTION=true`、`TESTING=false`、`APP_PORT=9000`、`VOLUME /app/data/`、`HEALTHCHECK` 用 healthcheck.sh、`ENTRYPOINT /app/run.sh` |

`entry.sh` 干五件事：按 `PUID`/`PGID` 调整用户 → 切 `/app` → 激活 `/opt/mealie` 虚拟环境 → 加载 Docker Secrets → `exec mealie`（对应 `[project.scripts] mealie = "mealie.main:main"`）。

健康检查核心一句：`curl -fsk ${PROTO}://127.0.0.1:${PORT}/api/app/about`。记住那句话：**容器进程存在不等于应用可用**，`docker compose ps` 里 `unhealthy` 就是这个区别的体现。

## 13. 服务器与域名准备

- 域名按年买（万网/阿里云/腾讯云/华为云等），部署在国内服务器必须做 ICP 备案（在买域名/服务器的平台办，约 12-15 个工作日），再做公安备案（beian.mps.gov.cn，1-2 个工作日）。没备案会被厂商管控，访问不了
- 着急可以先 IP 访问
- 配置参考：个人 1C1G1M / 2C2G2M；企业 4C4G 起；跑大模型要 GPU 机器，不是 ECS

## 14. 服务器目录与文件

统一放 `/opt/mealie`：

```text
/opt/mealie/
├── docker-compose.prod.yml    # 生产编排
├── .env.production            # 生产环境变量
├── nginx/conf.d/mealie.conf   # 反向代理配置
├── data/mealie/               # 应用数据（对应容器 /app/data）
├── postgres/data/             # 数据库数据
└── backups/                   # 备份
```

原则：数据库数据不能放临时目录，也不能只依赖容器内文件系统。

`.env.production` 关键项：`ALLOW_SIGNUP=false`、`PUID/PGID=1000`、`TZ=Asia/Shanghai`、`BASE_URL`（用户真实访问地址，HTTPS 就写 https）、`DB_ENGINE=postgres` + `POSTGRES_USER/PASSWORD/SERVER/PORT/DB`、`API_PORT=9000`、`LOG_LEVEL=INFO`、`OPENAI_API_KEY/BASE_URL/MODEL/REQUEST_TIMEOUT`。

必须改的三项：`BASE_URL`、`POSTGRES_PASSWORD`（不要还用 mealie）、`OPENAI_API_KEY`。`.env.production` 不进 Git，备份时注意权限。

## 15. 生产 compose 三容器

`docker-compose.prod.yml` 三个服务：

| 服务 | 关键配置 |
| --- | --- |
| `mealie` | `image: mealie:3.15.1-custom`、`env_file: .env.production`、`depends_on postgres(service_healthy)`、卷 `./data/mealie:/app/data`、端口 `127.0.0.1:9925:9000`、healthcheck 用 `/app/healthcheck.sh`（30s/10s/5 次/60s 启动宽限） |
| `postgres` | `postgres:15`、环境变量用 `${POSTGRES_*}` 插值、卷 `./postgres/data:/var/lib/postgresql/data`、healthcheck `pg_isready` |
| `nginx` | `nginx:1.27-alpine`、`depends_on mealie(service_healthy)`、`80:80` + `443:443`、挂 `./nginx/conf.d` 与 `/etc/letsencrypt`、同网络 |

四个关键点：

1. **启动必须带 `--env-file`**：`docker compose --env-file .env.production -f docker-compose.prod.yml up -d`。因为 `env_file` 只把变量传进容器，Compose 文件里的 `${POSTGRES_USER}` 这类插值需要 `--env-file` 在启动时读
2. **应用只监听本机** `127.0.0.1:9925:9000`，公网入口交给 Nginx；本机调试仍可用 9925
3. **两个数据卷必须挂**，否则删容器数据就没了
4. **`depends_on ... service_healthy`** 让应用等数据库就绪，减少启动顺序问题

## 16. 镜像构建与传输

服务器装 Docker（Ubuntu 官方源流程 → `apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin` → `systemctl status docker`）。

构建：项目根目录 `docker build -t mealie:3.15.1-custom -f docker/Dockerfile .`；只重打最终阶段加 `--target production`。

三种分发方式：

- 本地打包上传：`docker save -o mealie-xxx.tar` → `scp` 到服务器 → `docker load -i`
- 私有仓库：`docker tag` + `docker push`，compose 里换成仓库地址
- 服务器直接 build

## 17. Nginx 转发

`/opt/mealie/nginx/conf.d/mealie.conf` 核心：

```nginx
listen 80;
server_name 你的域名;
client_max_body_size 64m;
location / {
    proxy_pass http://mealie:9000;   # 容器名，不是 127.0.0.1:9925
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 300;
    proxy_send_timeout 300;
}
```

最容易错的一点：`proxy_pass` 必须写 **`http://mealie:9000`**（Compose 服务名 + 容器内端口），不能写 `127.0.0.1:9925`——Nginx 在容器里，127.0.0.1 是它自己。没有域名时 `server_name _;` 先顶上。

改完 `nginx -t` 检查、`nginx -s reload` 重载，两个命令都通过 `docker compose ... exec nginx` 在容器内执行。

## 18. 部署六步

1. 建目录（`/opt/mealie` 及 data/postgres/nginx/backups 子目录）
2. 放三个文件：`docker-compose.prod.yml`、`.env.production`、`nginx/conf.d/mealie.conf`
3. `docker compose --env-file .env.production -f docker-compose.prod.yml up -d`
4. `ps` 看状态：`mealie_app` 与 `mealie_postgres` 都应 running/healthy
5. `curl -i http://127.0.0.1:9925/api/app/about` 应 200；配好 Nginx 后域名同样应 200
6. 浏览器验证：首页 → 登录 → 建 Recipe → 传图 → 刷新数据还在 → 配了 OpenAI 的话去后台 debug 页测一下

## 19. HTTPS

前提是 Nginx 容器挂了证书目录：

```yaml
volumes:
  - ./nginx/conf.d:/etc/nginx/conf.d:ro
  - /etc/letsencrypt:/etc/letsencrypt:ro
```

**不要只挂 `/etc/letsencrypt/live`**：Let's Encrypt 的 live 目录是指向 archive 的符号链接，只挂 live 会导致容器内证书不可读。要挂整个 `/etc/letsencrypt`。

配置上加一个 80 跳 443 的 server（`return 301 https://$host$request_uri`），443 server 里配 `ssl_certificate .../fullchain.pem`、`ssl_certificate_key .../privkey.pem`、`X-Forwarded-Proto https`。改完 `.env.production` 的 `BASE_URL` 也要同步成 `https://...`——写错会导致邮件链接、分享链接、登录跳转异常。

## 20. 部署后的检查清单

| 检查项 | 命令/位置 | 看什么 |
| --- | --- | --- |
| 容器状态 | `compose ps` | State / Health / Ports |
| 健康接口 | `curl -i .../api/app/about` | 200 |
| 数据库 | `docker exec -it mealie_postgres psql -U mealie -d mealie` → `\dt` | 表存在 |
| 应用日志 | `docker logs --tail 200 mealie_app` | `database initialization`、`APP SETTINGS`、`APP FEATURES`、`OPENAI`、`ERROR`、`Traceback` |
| 页面功能 | 浏览器 | 登录、建/改 Recipe、传图、刷新、重启容器后数据仍在 |

## 21. 备份、升级、回滚

备份三件（最小集其实是五件）：

```bash
# 数据库
docker exec mealie_postgres pg_dump -U mealie -d mealie > /opt/mealie/backups/mealie-$(date +%F-%H%M%S).sql
# 应用数据
tar -czf /opt/mealie/backups/mealie-data-$(date +%F-%H%M%S).tar.gz -C /opt/mealie/data mealie
```

最小备份内容：PostgreSQL 数据、`/app/data` 映射目录、`.env.production`、`docker-compose.prod.yml`、Nginx 配置。

升级顺序（顺序本身就是重点）：备份库 → 备份数据 → 构建/拉新镜像 → 改 compose 里的 tag → `up -d` → 看健康 → 验核心功能。

回滚：`down` → 镜像 tag 改回旧版 → 确认数据库兼容或恢复备份 → `up -d` → 验证。**如果新版本执行了不可逆迁移，只切镜像不够**，这也是升级前必须备份的原因。

## 22. 六个常见故障

| 现象 | 排查顺序 |
| --- | --- |
| 页面打不开 | `ps` → 本机 curl → 本机通但域名不通就查 Nginx / 防火墙 / 云安全组 / 域名解析 |
| 容器一直重启 | `docker logs --tail 200 mealie_app`：库连不上、环境变量错、目录权限、镜像不完整、端口占用 |
| 数据库连不上 | `.env.production` 里 `POSTGRES_SERVER=postgres`（Compose 服务名，不是 localhost） |
| 登录/分享链接异常 | `BASE_URL` 是否写对（协议、域名） |
| 图片上传失败 | Nginx `client_max_body_size` 是否够；`/opt/mealie/data/mealie` 权限是否与 PUID/PGID 匹配（可 `chown -R 1000:1000`） |
| OpenAI 不可用 | `.env.production` 有 Key、重启后生效、服务器能出网、`OPENAI_REQUEST_TIMEOUT` 别太短；后台 Admin → Debug → OpenAI 可自测 |

## 23. 防火墙与配置边界

只开三个公网端口：`22`（SSH）、`80`、`443`。不对公网开：`5432`（PostgreSQL）、`9925`（内部映射）、`9000`（容器内端口）。`127.0.0.1:9925:9000` 比 `9925:9000` 安全，多了本机绑定这一层。

第一版**先不做**：Kubernetes、多副本、Redis、对象存储、自动扩缩容、复杂 CI/CD、多区域容灾。市场验证后再按序补：PG 独立机、Nginx 独立机、Mealie 多实例、统一日志、定时备份、证书自动续期、镜像仓库 + 自动部署。

## 24. 最小验收十条

1. `compose ps` 两个服务都在运行
2. `mealie` 健康检查 healthy
3. `postgres` 健康检查 healthy
4. `curl http://127.0.0.1:9925/api/app/about` 返回 200
5. 域名或 IP 能打开页面
6. 能登录或完成初始化
7. 能创建一条 Recipe
8. 重启容器后 Recipe 不丢
9. 能看应用日志
10. 能执行一次 PostgreSQL 备份

## 关键知识清单

- 在别人的项目里加 AI：先读现有 `OpenAIService`、Prompt 目录、Schema 基类，别复制一套新的
- AI 开关统一用 `settings.OPENAI_ENABLED`，不自己读环境变量
- Prompt 走点号路径 + 文件系统，`OpenAIDataInjection` 注入业务数据
- 返回一律结构化：新 Schema 继承 `OpenAIBase`，字段写清 description
- AI 输入用白名单序列化，不发 ID、settings、comments 这类无关字段
- Route 薄、Service 厚：开关判断 → 查数据 → 调 Service → 统一异常
- 前端类型是自动生成的，改后端后跑 `task dev:generate`，别手改
- 生产部署看四件事：多阶段镜像、entry.sh + healthcheck、数据卷、`--env-file`
- 容器间通信用 Compose 服务名（`mealie:9000`、`postgres:5432`），不是 localhost
- 应用端口绑 `127.0.0.1`，公网只留 22/80/443
- HTTPS 要挂整个 `/etc/letsencrypt`（live 是符号链接）
- 部署不是"跑起来就完事"：备份、升级、回滚流程齐了才算交付
