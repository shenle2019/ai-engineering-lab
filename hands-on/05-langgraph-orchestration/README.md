# 05 · LangGraph 编排实战：AI 行程管家

把课件 day13–day16 四讲（智能导游、核心架构与子图、记忆与中断、时间旅行与流式/持久执行）压缩成**一条可跑通的链路**，而不是四份互不相干的 demo：一个「AI 行程管家」从并行规划 → 预算评估 → 优化回边 → 人工审批 → 长期画像沉淀，一路走完。

## 来源

- 课件目录：`python山顶会三期/day13`、`day14`、`day15`、`day16` 四个压缩包
- 只提取源码类文件（跳过 venv、图片、嵌套压缩包），共 121 个 `.py`/`.json`/`.toml`
- 课件用 OpenAI + Postgres/内存后端；这里换成本机 DeepSeek + SQLite，其余概念一一对应

## 案例主线

```
START → load_profile（读长期画像）
          ├→ plan_attractions ┐   并行 fan-out，两条入边在 merge_cost 汇聚
          └→ plan_food ───────┴→ merge_cost
merge_cost → daily_detail（子图） → review_budget
review_budget ──达标──→ await_approval（interrupt 人工审批）→ save_profile → finalize → END
              └─超支──→ revise_plan（降档重算）→ review_budget（最多 2 轮）
```

设计取舍：**事实与价格交给离线知识库，只把文案交给模型**。课件里景点和费用全由 LLM 生成，价格每次不一样，预算判断跟着飘；这里景点门票、餐饮人均、住宿价都是常量表，LLM 只负责排顺序和写文案，于是「超支 → 优化 → 达标」这条回边才是可复现的。

## 目录结构

```
05-langgraph-orchestration/
├── lib/                 # 可复用核心
│   ├── llm.py           # 模型工厂（DeepSeek 兼容层）+ 结构化输出工厂
│   ├── state.py         # TypedDict 状态、reducer、pydantic schema
│   ├── knowledge.py     # 杭州/成都/西安 离线价格表 + estimate_cost
│   ├── nodes.py         # 10 个节点，每个只做一件事
│   ├── graphs.py        # 主图 + 逐日子图 + draw() 导出图结构
│   └── service.py       # langgraph.json 的服务入口
├── stages/              # 阶段脚本，按 s01…s10 递增，每个只验证一个环节
├── case/travel_concierge.py   # 综合案例 CLI
├── assets/              # 图结构导出（PNG，失败降级 .mmd）
├── logs/                # 每个阶段的实跑日志
├── requirements.txt
├── langgraph.json
└── .env.example
```

## 运行环境

| 项 | 值 |
| --- | --- |
| 系统 | Windows 11 22H2 / PowerShell |
| Python | 3.11.9（venv） |
| langgraph | 1.2.20 |
| langchain / core | 1.4.10 / 1.7.7 |
| langchain-openai | 1.7.4 |
| langgraph-checkpoint(-sqlite) | 4.3.1 / 3.1.3 |
| 服务化 | langgraph-cli 0.4.42 + langgraph-api 0.17.1 |
| 模型 | DeepSeek `deepseek-chat`（走 ChatOpenAI 兼容层） |

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env   # 填 DEEPSEEK_API_KEY
```

## 阶段脚本与验证结果

每个脚本都真跑过，日志在 `logs/`，图结构在 `assets/`。

| 脚本 | 验证点 | 结果 |
| --- | --- | --- |
| `s01_state_graph.py` | 状态合并、`Annotated + operator.add` 追加、条件边回环、END 收口 | 预算 2000 触发 `estimate → review 超支 → downgrade 1260 → review 达标 → confirm`，`S01 OK` |
| `s02_graph_and_functional_api.py` | Graph API 六步 ReAct（llm↔tool 回边）与 Functional API（`@task`/`@entrypoint`）等价 | 3+4=7、7×2=14；12/3=4、4+10=14，各 3 次模型调用，`S02 OK` |
| `s03_workflow_patterns.py` | 六种工作流模式 + 每种模式的调用计数 | 16 次调用，评估者-优化器 2 轮收敛，`S03 OK` |
| `s04_subgraphs.py` | 子图两挂法、持久化继承、`subgraphs=True` 流式 | 检出父图 `checkpoint_ns=''` 与子图 `subgraph:<task_id>` 两类检查点，`S04 OK` |
| `s05_memory.py` | 短期记忆（thread 隔离）、`trim_messages`、`RemoveMessage`、长期 store 跨 thread | 同 thread 4 条消息含历史 / 换 thread 只 2 条；修剪 8→4、清空后 0；t2 读到 t1 画像，`S05 OK` |
| `s06_interrupts.py` | 批准拒绝、审查编辑、工具内中断、非法输入重试 | 四种形态均暂停并恢复，`S06 OK` |
| `s07_time_travel.py` | 重放、`update_state` 分支、子图粒度历史 | 重放使 `write_joke`/`review` 各多跑一次；分支后旧分支 4 个快照仍在；子图 3 个检查点可单独读，`S07 OK` |
| `s08_streaming.py` | `updates` / `messages`(v2) / 组合模式 / 按节点过滤 | 令牌块 24 + 19，节点事件 `['write_joke','write_poem']`，`S08 OK` |
| `s09_durable_execution.py` | 崩溃续跑只补未完成节点、标记位幂等 | `prepare` 始终 1 次、`write` 2 次（失败 1 + 成功 1）、`notify` 跑 2 次只发 1 条，`S09 OK` |
| `s10_service_api.py` | `langgraph dev` 暴露 HTTP：`/ok → /assistants/search → /threads → /runs/wait → resume` | 成都 3 天 1800 元，`/runs/wait` 收到 interrupt（预估 997 元），resume 后出终稿，`S10 OK` |

综合案例：

| 命令 | 验证点 |
| --- | --- |
| `python case/travel_concierge.py --budget 900 --auto-approve --fork-budget 5000` | 1129.5 超支 → 第 1 轮降档 747.5 达标 → 审批 → 沉淀画像；时间旅行把预算改 5000 从 `merge_cost` 前重开分支 |
| `python case/travel_concierge.py --thread trip-stream-1 --budget 3000 --stream --auto-approve` | 令牌级流式打印 + 流式下的 interrupt 捕获 |
| `python case/travel_concierge.py --thread trip-pause-1 --budget 2800` | 无终端输入时停在审批点，`（没有终稿）` |
| `python case/travel_concierge.py --thread trip-pause-1 --resume --auto-approve` | 同一 thread 续跑到 `finalize` |

服务化另需一个终端：

```powershell
$env:PYTHONUTF8="1"        # Windows 必带，否则 langgraph_api 读 OpenAPI 文件按 GBK 解码报错
langgraph dev --port 2024 --no-browser
```

## 踩坑记录

1. **DeepSeek 不支持 `response_format=json_schema`**：`with_structured_output()` 默认走 json_schema，直接 400 `This response_format type is unavailable now`。统一改成 `method="function_calling"`，封在 `lib/llm.py: structured()` 里。
2. **Literal 不能直接当 function calling 的 schema**：`with_structured_output(Literal[...], method="function_calling")` 报 `Literal[...] is not a module, class, method, or function`。包一层 pydantic `TopicChoice` 才行。
3. **`messages` 通道必须用 `add_messages`**：用 `operator.add` 时 `RemoveMessage(REMOVE_ALL_MESSAGES)` 只是一条普通消息被追加，清空后还剩 2 条。
4. **子图当节点挂载会重复写回**：子图输入继承了父图已累积的 `log`，结束时又把整份写回，reducer 再追加一次，`preclean` 出现两次。要么子图用私有 key，要么只返回新增部分。
5. **`update_state` 不是「开新线程」**：它把新检查点写在同一 thread 上并把线程头挪过去，旧检查点仍在历史里；要互不干扰得换 thread_id。
6. **带 checkpoint_id 的 config 不能用来 resume**：`Command(resume=...)` 必须走线程头（只带 thread_id），否则会从旧点重跑而不是接住 interrupt。
7. **流式模式下 interrupt 不在返回值里**：它作为一条 `updates` 块（key `__interrupt__`）吐出，不手动捕获就再也 resume 不了。
8. **子图历史要看全量得去掉 checkpoint_id**：只给 `checkpoint_id` 只能看到那一点，只留 `checkpoint_ns` 才能列出子图完整历史。
9. **`langgraph dev` 加载入口是单文件模块**：`from .graphs import ...` 报 `attempted relative import with no known parent package`，要 `sys.path` 插入项目根后绝对导入。
10. **服务端会自己注入 checkpointer/store**：入口里再传一份会被判为冲突，`lib/service.py` 编译时不带持久化。
11. **context_schema 字段必须有默认值**：HTTP 调用不传 context 时框架拿空 dict 构造 dataclass，`user_id: str` 直接 TypeError。
12. **`langgraph dev` 在 Windows 上两个前置**：`pip install colorama`（structlog 彩色渲染）+ `PYTHONUTF8=1`（OpenAPI 文件解码）。
13. **`GET /assistants` 是 405**：列表接口是 `POST /assistants/search`。

## 与课件的取舍

- 保留：状态图/reducer/条件边、Send 扇出、两套 API、七种工作流模式、子图两挂法、短期+长期记忆、四种 interrupt、时间旅行三类用法、流式三种读法、SQLite 持久执行、`langgraph.json` 服务化。
- 改动：景点与价格改为离线知识库（课件由 LLM 自由生成，预算不可复现）；课件 Postgres 换 SQLite；课件 OpenAI 换 DeepSeek；课件的 `langgraph_demo001` 工程只借鉴 `langgraph.json` + `service.py` 入口形式，不搬运脚手架。
- 未做：LangSmith 托管部署、Postgres/Redis 后端、Studio UI 实操（需联网登录）。

## 已知限制

- 长期记忆用 `InMemoryStore`，进程退出即丢；换 Redis/Postgres store 只改 `build_runtime()` 一行。
- `--fork-budget` 分支重跑会把 `trace` 里的节点记录再追加一遍，这是 reducer 的正常表现，不是 bug。
