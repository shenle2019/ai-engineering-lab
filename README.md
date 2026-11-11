# AI Engineering Lab

Python 山顶会三期的学习仓库：**课件笔记** + **实操复刻记录** 两条线并行。

- `notes/`：从课件提炼的知识笔记，文件名以 `01-`～`12-` 前缀标出学习顺序，只记录理解，不复刻代码
- `hands-on/`：按课件自己重写并跑通的实操，目录名同样带顺序前缀，每个实操一个子目录，附带源码、脚本和运行日志

## 课程地图与进度

| 阶段 | 课次 | 主题 | 笔记 | 实操 |
| --- | --- | --- | --- | --- |
| 环境基础 | 预习1 | Linux 入门操作（命令、权限、软硬链接、vim、服务、进程） | 01-Linux与Docker容器化基础.md | 01-linux-docker-compose-deploy |
| 环境基础 | 预习2 | Docker 从入门到精通（镜像、容器、Dockerfile、迁移备份） | 同上 | 同上 |
| 环境基础 | 预习3 | Docker Compose 详解（服务、项目、多容器编排） | 同上 | 同上 |
| 工具调用 | day01 | Function Calling 之 AI 股票小助手和 MCP | 02-FunctionCalling与FastMCP-MCP协议与服务端开发.md | 02-function-calling-and-fastmcp |
| 工具调用 | day02 | FastMCP 从入门到精通 | 同上 | 同上 |
| LangChain | day03 | LangChain v1.2.9 核心组件之 Agents 和 Models | 03-LangChain框架概览与Agents智能体入门.md | 03-langchain-agent-engineering |
| LangChain | day04 | LangChain 核心之 Models 模型和 Messages 消息 | 04-LangChain模型接入与消息体系.md | 同上 |
| LangChain | day05 | LangChain 结构化输出和流式输出 | 05-LangChain流式传输与结构化输出.md | 同上 |
| LangChain | day06 | LangChain 高级组件之工具 / 短期记忆 / 护栏 / MCP / 人机交互 | 06-LangChain工具-短期记忆-护栏-MCP与人机交互.md | 同上 |
| LangChain | day07 | LangChain 高级组件之中间件 / 运行时 / 上下文工程 / 长期记忆 | 07-LangChain中间件-长期记忆-上下文工程与多智能体.md | 同上 |
| 项目二次开发 | day08 | GitHub 项目二次开发与 Mealie 本地部署（工具链、Git、uv、Docker） | 08-GitHub项目二次开发与Mealie本地部署.md | 04-mealie-second-dev-and-prod-deploy |
| 项目二次开发 | day09 | Mealie 项目结构与 uv / yarn 本地开发 | 09-Mealie项目结构与uv本地开发环境.md | 同上 |
| 项目二次开发 | day10 | Mealie 源码分析：启动、配置、路由与数据模型 | 10-Mealie源码分析-启动配置路由与数据模型.md | 同上 |
| 项目二次开发 | day11 | Nuxt 框架与 Mealie 字段扩展二次开发 | 11-Nuxt框架与Mealie字段扩展二次开发.md | 同上 |
| 项目二次开发 | day12 | AI 功能二次开发与生产环境部署 | 12-Mealie的AI摘要功能开发与生产部署.md | 同上 |
| LangGraph | day13 | LangGraph 之智能导游案例与本地服务 | 待做 | 待做 |
| LangGraph | day14 | LangGraph 核心架构模式和子图 | 待做 | 待做 |
| LangGraph | day15 | LangGraph 之子图 / 记忆 / 中断 / 持久化 | 待做 | 待做 |
| LangGraph | day16 | LangGraph 之时间旅行 / 流式处理 / 持久执行 | 待做 | 待做 |
| 工程化 | day17 | Skill 从入门到精通 | 待做 | 待做 |

## 已完成内容

### 笔记

| 文件 | 覆盖内容 |
| --- | --- |
| [notes/01-Linux与Docker容器化基础.md](notes/01-Linux与Docker容器化基础.md) | 预习1–3：Linux 发行版与常用命令、权限与链接、vim、systemd、进程；Docker 镜像/容器/数据卷/Dockerfile；Compose 服务编排 |
| [notes/02-FunctionCalling与FastMCP-MCP协议与服务端开发.md](notes/02-FunctionCalling与FastMCP-MCP协议与服务端开发.md) | day01–day02：Function Calling 七步流程与 tools 说明书、反射调用与二次请求消息结构；MCP 架构与三种传输方式（Streamable HTTP / stdio / SSE 弃用）、生态入口、12306 server 部署；FastMCP 三大组件 Tool/Resource/Prompt、中间件、三种客户端接入；AI 股票小助手（东方财富接口）与 AI PC 助手（注册表读软件）两个案例 |
| [notes/03-LangChain框架概览与Agents智能体入门.md](notes/03-LangChain框架概览与Agents智能体入门.md) | day03：LangChain 定位与发展史（0.3 到 1.0 的断层）、家族七件套选型、安装与版本锁定；`create_agent` 三要素（模型字符串 vs 模型对象、`@tool` 与 docstring、静态/动态提示词）；动态模型中间件、结构化输出两策略、自定义 state 短期记忆、`values` 流式；中间件钩子预告 |
| [notes/04-LangChain模型接入与消息体系.md](notes/04-LangChain模型接入与消息体系.md) | day04：Models 四种对接方式（ChatOpenAI / init_chat_model / 官方包 / ChatTongyi）与「官方包 vs 兼容层只差思考过程」；参数与方法、裸 Model 的工具调用五小节、结构化输出四形态、高级主题十一项（多模态、profile、reasoning、Ollama、服务端工具、限流、代理、logprobs、token 统计、RunnableConfig、可配置模型）；Messages 四类型、三种写法、`content_blocks` 标准块全清单与多模态三种来源 |
| [notes/05-LangChain流式传输与结构化输出.md](notes/05-LangChain流式传输与结构化输出.md) | day05：流式四模式（updates 节点进度 / messages token / custom 工具进度 / values 整状态）、多模式组合与模型级禁用；Agent 层结构化输出的 `response_format` 四取值、两大策略原理与代价、`structured_response` 取法、Union 与 schema 校验两类自动纠错、`handle_errors` 六档 |
| [notes/06-LangChain工具-短期记忆-护栏-MCP与人机交互.md](notes/06-LangChain工具-短期记忆-护栏-MCP与人机交互.md) | day06：工具三种精细度与 `args_schema`、`ToolRuntime` 六件套（state/context/store/stream_writer/config/tool_call_id）、ToolNode 与预构建/服务端工具；短期记忆 checkpointer+thread_id、数据库持久化、超限四策略（修剪/删除/总结/自定义）；护栏两类方法与 PIIMiddleware、自定义 before/after 钩子；MCP 三种传输与 `get_tools()` 适配；HITL 三种决策与中断恢复 |
| [notes/07-LangChain中间件-长期记忆-上下文工程与多智能体.md](notes/07-LangChain中间件-长期记忆-上下文工程与多智能体.md) | day07：中间件四类能力、内置十六个、六个钩子与 `jump_to` 声明、包装式短路/重试、`request.override` 动态换模型；长期记忆 namespace+key 结构与 put/get/search；Runtime 三件套与三处访问点；上下文工程三类来源与三个动态提示手法；多智能体两种做法（Agent 当工具 / LangGraph + Command 交接）；RAG 动机与概念 |
| [notes/08-GitHub项目二次开发与Mealie本地部署.md](notes/08-GitHub项目二次开发与Mealie本地部署.md) | day08：七步二次开发路径；AI 编辑器定位（Codex / Claude Code）与自定义指令；Git 概念、命令表与三个实操场景（含浅克隆）；uv 五命令与拿新项目的五步检查；Docker 五概念、compose 五问与「ps → logs → exec」排查顺序；DeepWiki / NotebookLM；Mealie 目录、两种运行方式、四个关键配置、9091→9000 与默认账号、启动链路、六类常见问题 |
| [notes/09-Mealie项目结构与uv本地开发环境.md](notes/09-Mealie项目结构与uv本地开发环境.md) | day09：读陌生项目的文件链；顶层 / 后端 / 前端三张职责表；uv `--extra pgsql --group dev` 本地依赖与三条经验；`yarn` + `yarn dev` 前端启动；本地开发 = 后端 uv + 前端 yarn，Docker 仍是最小验证；启动时 init_db 与登录失败先查初始化；答疑（Claude Code vs Codex、临时邮箱换域名） |
| [notes/10-Mealie源码分析-启动配置路由与数据模型.md](notes/10-Mealie源码分析-启动配置路由与数据模型.md) | day10：十三步阅读顺序；后端目录职责；`main.py`（uvicorn）与 `app.py`（FastAPI、中间件、`api_routers()`、`lifespan_fn` → `init_db.main()` + `start_scheduler()`）；`core/config.py` 与 `AppSettings` 字段表、`OPENAI_FEATURE`；自建 fast_model demo 的三层路由写法；总路由 `/api`；recipe 模块与六层调用链；`RecipeModel` 四类字段与关联、Schema 四类、前端对应路径 |
| [notes/11-Nuxt框架与Mealie字段扩展二次开发.md](notes/11-Nuxt框架与Mealie字段扩展二次开发.md) | day11：Nuxt 定义与 Nuxt2/Nuxt3+ 版本对应、五特性与 Vue 对比、适用边界；约定式目录；文件路由映射、动态/可选/通配、`NuxtLink`、嵌套路由与 `definePageMeta`；三类中间件；布局（`<NuxtPage />`、`layout: false`、`useLayoutData`）；组件与 composable 自动导入（目录前缀、`_` 排除）；difficulty 需求六问 → ORM → alembic 迁移 → Schema → 路由/服务 → 前端五步 |
| [notes/12-Mealie的AI摘要功能开发与生产部署.md](notes/12-Mealie的AI摘要功能开发与生产部署.md) | day12 上半：复用 `OpenAIService`（get_client / 点号 get_prompt / `OpenAIDataInjection` / `response_schema`）、`OpenAIBase` 与 Prompt 目录、三个现成案例；`POST /api/recipes/{slug}/ai-summary` 设计与不落库理由、白名单序列化、`OpenAIRecipeSummary`、Prompt 六条边界、Service + 薄 Route、前端 API/组件/i18n、五项手动验证与十五步顺序。下半：多阶段 Dockerfile 四段、entry.sh 与 healthcheck、`/opt/mealie` 目录、`.env.production`、compose prod 三容器（`127.0.0.1:9925:9000`、`--env-file` 插值）、Nginx 用服务名转发、HTTPS 挂整个 letsencrypt、备份/升级/回滚、防火墙与最小验收十条 |

### 实操

| 目录 | 内容 | 验证方式 |
| --- | --- | --- |
| [hands-on/01-linux-docker-compose-deploy](hands-on/01-linux-docker-compose-deploy) | 把预习三课串成一条链路：Linux 基础操作 → redis/nginx 单容器 → Dockerfile 构建 Flask 访问计数应用 → Compose 编排 redis+web+nginx → 镜像 commit/save/load 迁移 | 在本机 WSL2 Ubuntu 24.04 + Docker 29.1.3 真机跑通，5 个阶段脚本 + 运行日志存于目录内 |
| [hands-on/02-function-calling-and-fastmcp](hands-on/02-function-calling-and-fastmcp) | 把 day01–day02 串成一条链路：手工 Function Calling 七步 → 东方财富行情工具（字段校准）→ FastMCP 发布为 MCP server（两种传输、三组件、中间件）→ PC 文件助手 → LLM 经 MCP Host 调工具 | 本机 Windows + Python 3.11 + fastmcp 2.14.7 + DeepSeek 真跑，7 个阶段脚本 + 运行日志存于目录内；同时修正了课件中 f43 除数、f116 含义两处错误 |
| [hands-on/03-langchain-agent-engineering](hands-on/03-langchain-agent-engineering) | 把 day03–day07 串成一条电商售后客服案例：Agents/Models/Messages 基础 → 四种流式模式与结构化输出纠错 → ToolRuntime/短期记忆/PII 与自定义护栏 → FastMCP 工具经 MCP 接入 → HITL 退款审批 → 中间件与长期记忆与上下文工程 → 两种多智能体做法 → 综合案例（护栏+双记忆+HITL+多智能体+流式+工单结构化输出） | 本机 Windows + Python 3.11.9 + LangChain 1.4.9 + DeepSeek 真跑，7 个阶段脚本 + 1 个综合案例 + 8 份运行日志存于目录内 |
| [hands-on/04-mealie-second-dev-and-prod-deploy](hands-on/04-mealie-second-dev-and-prod-deploy) | 把 day08–day12 串成一条 Mealie 二次开发链路：字段扩展 difficulty（迁移→ORM→Schema→路由→前端）→ AI 摘要接口（OpenAIRecipeSummary + Prompt + DeepSeek JSON 模式降级 + 前端卡片）→ 生产部署（多阶段 Dockerfile + Compose 三容器 + nginx 反代 + 重启不丢数据 + pg_dump） | 本机 WSL2 Ubuntu 24.04 + Docker 29.1.3 + PostgreSQL 15 + Nuxt 4 真跑：镜像构建 52 步成功、三容器 healthy、difficulty 与 AI 摘要走 nginx 全链路 200、12 份日志 + 完整改动 patch 存于目录内 |

## 运行环境

两套环境按实操类型分工，互不影响：

**环境与部署类**（WSL2 + Docker）：

| 项 | 版本 |
| --- | --- |
| WSL2 发行版 | Ubuntu 24.04.5 LTS（rootfs 离线导入，D 盘） |
| Linux 内核 | 6.18.54.1-microsoft-standard-WSL2 |
| Docker Engine | 29.1.3（systemd 托管，overlayfs） |
| Docker Compose | v2.40.3 |
| 镜像加速 | docker.m.daocloud.io / docker.1ms.run / docker.1panel.live |
| apt / pip | 清华源 |

课件用 CentOS + VMware，这里用 Ubuntu + WSL2 等价替代：`yum/dnf` ↔ `apt`，`systemctl` 用法一致。

**工具调用 / 框架类**（Windows + Python venv）：

| 项 | 版本 |
| --- | --- |
| Python | 3.11.9（fastmcp / LangChain 1.x 均要求 ≥3.10，系统默认 3.8 不可用） |
| fastmcp | 2.14.7（`fastmcp<3`，function-calling-and-fastmcp 用） |
| LangChain / LangGraph | langchain 1.4.9、langgraph 1.2.20、langchain-mcp-adapters 0.3.2、mcp 1.30.0（langchain-agent-engineering 用） |
| LLM | DeepSeek `deepseek-chat`（OpenAI 兼容），key 只走环境变量 |
| 外部数据 | 东方财富公开行情接口（匿名、只读、低频） |

## 约定

- 笔记文件按知识点命名，用 `01-`～`12-` 数字前缀表示学习顺序，不带 `dayXX`、`预习X` 这类课次前缀
- 实操目录按关键知识点命名，同样带顺序前缀（`01-`、`02-`、`03-`、`04-`），一个实操一个子目录，内含源码、脚本、日志
- 只记录真跑通的内容；没跑起来的部分在对应 README 里写明现象与已尝试步骤
- 目录名统一英文 kebab-case，避免中文路径在 URL 中被编码
