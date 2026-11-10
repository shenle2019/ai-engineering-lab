# Mealie 源码分析：启动、配置、路由与数据模型

> 来源：python 山顶会三期 day10（`day10/day02.md`，源码分析；day11 里的同名文件为修订版）
> 定位：从入口到数据表走通一条完整调用链，为后面加字段、加 AI 接口做准备

## 总览

这节课只做一件事：**用固定顺序把一个 FastAPI 项目读明白**。顺序是"先知道怎么跑 → 再知道接口怎么进 → 再知道业务怎么处理 → 最后知道数据怎么存、页面怎么展示"。中途用一个自建的小 FastAPI 例子（多任务模型服务）演示企业里常见的路由分层写法，再回到 Mealie 逐层对照。

## 1. 推荐的阅读顺序

课件给的文件链：

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

抽象成一句话：**入口文件 → 配置文件 → 路由入口 → 目标业务路由 → 模型与 Schema → 服务层与仓储层**。

## 2. 后端核心目录

| 路径 | 作用 |
| --- | --- |
| `mealie/app.py` | FastAPI 应用初始化入口 |
| `mealie/main.py` | 偏生产环境的运行入口 |
| `mealie/core/` | 配置、日志、安全、依赖注入 |
| `mealie/routes/` | 路由层，定义接口入口 |
| `mealie/services/` | 业务处理逻辑 |
| `mealie/repos/` | 数据访问层 |
| `mealie/db/` | 数据库初始化、Alembic、模型定义 |
| `mealie/schema/` | Pydantic 数据结构 |
| `mealie/middleware/` | 中间件 |
| `mealie/assets/` | 项目资源文件 |

## 3. 启动入口与初始化流程

### 3.1 `mealie/main.py`

职责很单一：调用 `uvicorn.run(...)`。特点：

- 以 `mealie.app:app` 为启动对象
- 读 `settings.API_HOST`、`settings.API_PORT`
- 支持日志配置与 TLS 证书配置

可以理解为"偏正式启动入口"。

### 3.2 `mealie/app.py`

真正的应用对象、路由挂载、中间件注册、生命周期逻辑都在这里。重点看五处：

1. `settings = get_app_settings()` 读全局配置
2. `app = FastAPI(...)` 创建应用
3. `lifespan_fn` 处理启动/关闭逻辑
4. `app.add_middleware(...)` 注册 GZip、Session、Locale 等中间件
5. `api_routers()` 挂载总路由、媒体路由、工具路由

### 3.3 启动过程

`lifespan_fn` 说明应用起来之后还有初始化动作，至少两件：

```python
import mealie.db.init_db as init_db
init_db.main()          # 数据库初始化
await start_scheduler() # 调度器启动
```

所以启动日志长是正常的：里面不只有 HTTP 服务，还有数据库检查、默认数据创建、定时任务注册、配置与功能状态打印。

## 4. 配置系统

### 4.1 配置入口

```text
mealie/core/config.py
mealie/core/settings/settings.py
```

`config.py` 负责"把配置读进来并组装好"：确定项目根目录、加载 `.env`、判断 `PRODUCTION`/`TESTING`、计算数据目录、构造 `AppSettings`。

### 4.2 `settings.py` 优先关注的字段

| 配置项 | 作用 |
| --- | --- |
| `BASE_URL` | 站点访问地址 |
| `API_HOST` / `API_PORT` | API 监听地址与端口 |
| `LOG_LEVEL` | 日志级别 |
| `DB_ENGINE` | 数据库类型，默认 `sqlite`，支持 `postgres` |
| `DB_URL` / `DB_URL_PUBLIC` | 数据库连接信息 |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | 大模型密钥与模型名 |
| `OPENAI_REQUEST_TIMEOUT` | OpenAI 请求超时 |
| `WORKERS` | Uvicorn worker 数量 |

### 4.3 OpenAI 判断

`AppSettings.OPENAI_FEATURE` 会检查 `OPENAI_API_KEY` 与 `OPENAI_MODEL` 是否齐全；不齐就不认为 OpenAI 可用。后面写 AI 功能时，判断开关统一用这个属性，不要自己读环境变量。

## 5. 路由层结构

多层路由在团队协作里的价值：不同业务放不同模块，互不干扰。

### 5.1 一个最小分层示例（课件自建 demo）

课件用一个"多任务模型服务"演示企业写法，目录结构与职责：

```text
app/
├── main.py                  # 应用入口，只挂总路由
├── schemas.py               # 请求/响应模型
├── core/model_registry.py   # 模型注册与获取
├── routers/
│   ├── api.py               # 最外层路由 /api
│   ├── health.py            # 模块路由 /health
│   └── predict.py           # 模块路由 /predict
└── services/predictor.py    # 业务处理
run.py                       # 启动脚本
```

关键约定：`health.py` 只写 `APIRouter(prefix="/health")`；`api.py` 用 `APIRouter(prefix="/api")` 把模块路由 `include_router` 进来；`main.py` 只负责创建应用、注册启动事件、挂总路由。启动时 `init_models()` 预热模型，服务层只做"拿模型 + 推理"，不碰 HTTP 细节。

这套写法就是 Mealie 路由层的缩小版：**路由文件只管收参和返回，业务逻辑下沉到 service**。

### 5.2 总路由入口

`mealie/routes/__init__.py` 把各模块路由统一挂到总路由：

```python
router = APIRouter(prefix="/api")
router.include_router(app.router)
router.include_router(auth.router)
router.include_router(users.router)
router.include_router(households.router)
router.include_router(groups.router)
router.include_router(recipe.router)
...
```

三个结论：API 总前缀是 `/api`；按业务域拆路由；找接口先找对应业务目录。

### 5.3 路由目录与 recipe 模块

`mealie/routes/` 目录很多，第一遍只读这几类：`auth/`（登录认证）、`users/`（用户）、`recipe/`（菜谱）、`households/`（家庭、购物清单、餐食计划）、`groups/`（组管理）、`admin/`（管理后台）、`media/`（媒体）、`explore/`（公开数据）。

`routes/recipe/` 重点文件：`recipe_crud_routes.py`（增删改查主接口）、`_base.py`（控制器公共能力）、`bulk_actions.py`（批量操作）、`shared_routes.py`（分享）、`exports.py`（导出）、`timeline_events.py`（时间线）。

## 6. 业务链路

### 6.1 核心业务对象

`Recipe` 是 Mealie 的核心：菜谱是主体数据，购物清单、餐食计划、收藏、分享、评论都围着它转。先把 Recipe 看明白，其他模块会轻松很多。

### 6.2 第一链路

从 `recipe_crud_routes.py` 能看到 `create_one`、`get_one`、`update_one`、`patch_one`、`delete_one`；从 `_base.py` 的 `BaseRecipeController` 能看到四个关键属性：

```python
self.recipes
self.group_recipes
self.group_cookbooks
self.service   # -> RecipeService(...)
```

说明路由层不把逻辑全写在接口函数里，核心处理交给服务层。

### 6.3 典型调用链

以"读取某个菜谱详情"为例：

```text
路由文件
-> BaseRecipeController / RecipeController
-> RecipeService
-> RepositoryRecipes
-> RecipeModel
-> Recipe / RecipeSummary Schema
```

对应文件：

```text
mealie/routes/recipe/recipe_crud_routes.py
mealie/routes/recipe/_base.py
mealie/services/recipe/recipe_service.py
mealie/repos/repository_recipes.py
mealie/db/models/recipe/recipe.py
mealie/schema/recipe/recipe.py
```

## 7. 数据模型分析

### 7.1 `RecipeModel`

文件：`mealie/db/models/recipe/recipe.py`，主表 `recipes`。字段分四类看：

- **标识与关系**：`id`、`slug`、`group_id`、`user_id`
- **基础展示**：`name`、`description`、`image`
- **时间与份量**：`total_time`、`prep_time`、`cook_time`、`recipe_yield`、`recipe_servings`
- **业务扩展**：`tags`、`recipe_category`、`tools`、`notes`、`assets`、`comments`、`timeline_events`

### 7.2 关联关系

`RecipeModel` 不是孤立表，至少与这些对象有关：`Category`、`Tag`、`Tool`、`RecipeIngredientModel`、`RecipeInstruction`、`Nutrition`、`RecipeComment`、`RecipeTimelineEvent`、`Household`、`User`。数据库层面它是一个"中心对象"。

### 7.3 Schema 层

模型定义"数据库怎么存"，Schema 定义"接口怎么收、怎么出"。重点文件 `mealie/schema/recipe/recipe.py`，四个类：

| 类名 | 作用 |
| --- | --- |
| `CreateRecipe` | 创建菜谱的输入结构 |
| `RecipeSummary` | 列表或简化返回结构 |
| `Recipe` | 详情结构，字段最完整 |
| `RecipePagination` | 分页返回结构 |

**二次开发加字段时，数据库模型、Schema、接口、前端四处必须同步改**，这是后面 day11 的前提。

## 8. 前端对应关系

只看后端容易不知道字段最终显示在哪。前端页面目录 `frontend/pages/`，Recipe 相关重点看：

```text
frontend/pages/g/[groupSlug]/r/[slug]/index.vue   # 菜谱详情页
frontend/pages/g/[groupSlug]/r/create/new.vue     # 新建菜谱页
frontend/components/Domain/Recipe/                # Recipe 公共组件
```

给 Recipe 加新字段，除了后端改造，最终一定要回到这几个路径补展示或录入。

## 关键知识清单

- 读源码的顺序：入口 → 配置 → 路由 → 业务 → 模型/Schema → 前端
- `main.py` 管启动（uvicorn），`app.py` 管应用对象、中间件、路由、生命周期
- 启动时 `init_db.main()` + `start_scheduler()`，所以日志长、初始化重
- 配置入口 `core/config.py` + `core/settings/settings.py`；AI 开关统一用 `OPENAI_FEATURE`
- 路由分层：模块 `APIRouter` + 总路由 `include_router`，前缀集中在 `/api`
- Recipe 是核心业务对象，调用链：路由 → 控制器 → Service → Repository → Model → Schema
- 模型管"怎么存"，Schema 管"怎么收返"，加字段必须两边都改
- 前端入口：详情页 `pages/g/[groupSlug]/r/[slug]/index.vue`，组件在 `components/Domain/Recipe/`
