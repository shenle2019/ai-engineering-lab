# LangChain Agent 工程化实操（day03–day07）

> 来源：python 山顶会三期 day03–day07（LangChain v1.2.9 核心组件 → 高级组件）
> 定位：把五节课的能力按「从单体 Agent 到可控多智能体」重写成一条案例线，全部本机真跑，日志随目录提交
> 对应笔记：`notes/03-LangChain*` ～ `notes/07-LangChain*` 五篇（理解向记录，与本目录互相印证）

## 1. 案例主线

核心目标：做一个**电商售后智能客服**，能查订单、能退款、能记住用户偏好、能回答政策问题，且危险操作必须人工审批。

| 阶段脚本 | 对应课次 | 复刻内容 | 关键验证点 |
| --- | --- | --- | --- |
| `stages/s01_agent_basics.py` | day03 | `create_agent` 三要素、`@tool`、动态提示词、基础结构化输出 | 工具调用闭环；vip 打 9 折、普通不打折；`structured_response` 可取 |
| `stages/s02_models_messages.py` | day04 | 官方包 vs OpenAI 兼容层、裸 Tool Calling 循环、Messages 体系、可配置模型 | 手写两轮工具循环；`tool_calls`/`ToolMessage` 结构；chunk 可相加；`config_prefix` 切到 reasoner 后出现 `reasoning` 内容块 |
| `stages/s03_streaming_structured.py` | day05 | 四种流式模式、多模式组合、结构化输出与纠错 | updates/messages/custom/多模式全部产出；`field_validator` 触发 1 次校验失败后自动重试成功 |
| `stages/s04_tools_memory_guard.py` | day06 前半 | `ToolRuntime`、`Command` 写状态、短期记忆、PIIMiddleware、自定义护栏 | 同 thread 记得姓名、换 thread 忘记；邮箱 redact、卡号 mask、api_key block；违禁词命中时模型调用 0 次 |
| `stages/s05_mcp_hitl.py` | day06 后半 | FastMCP stdio 服务端 + `get_tools()`、HITL 审批 | MCP 工具算出 294；中断时退款未执行，approve 后执行；reject 后不执行 |
| `stages/s06_middleware_longmem.py` | day07 前半 | 内置重试中间件、自定义日志/动态换模型中间件、store、上下文工程 | 工具失败自动重试成功；按问题长度切换 chat/reasoner；动态提示词随用户与角色变化 |
| `stages/s07_multiagent.py` | day07 后半 | Agent 当工具、LangGraph + `Command(goto, graph=PARENT)` 交接 | 主管分别调售前/售后专家；入口路由 presale 后最终 `active_agent=aftersale` |
| `case/customer_service_agent.py` | day03–day07 综合 | 护栏 + 动态提示 + 短期/长期记忆 + HITL + 多智能体 + 流式 + 工单结构化输出 | 退款先中断后执行；偏好跨会话可读；政策问题交给专家；工单字段齐全 |

## 2. 运行环境

| 项 | 版本 / 说明 |
| --- | --- |
| OS | Windows 10/11（PowerShell 5.1） |
| Python | 3.11.9（系统默认 3.8 跑不了 LangChain 1.x，需 ≥3.10） |
| LangChain | 1.4.9（课件 1.2.9；本实操用到的 API 在 1.4.9 全部可用） |
| LangGraph | 1.2.20 |
| MCP | mcp 1.30.0 + langchain-mcp-adapters 0.3.2 |
| 模型 | DeepSeek `deepseek-chat` / `deepseek-reasoner`，key 只走环境变量 `DEEPSEEK_API_KEY` |
| 依赖安装 | `pip install -r requirements.txt`（国内建议加 `-i https://pypi.tuna.tsinghua.edu.cn/simple`） |

## 3. 目录结构

```
langchain-agent-engineering/
├── lib/llm.py                 # 模型工厂：ChatDeepSeek 与 ChatOpenAI 兼容层两条路
├── stages/                    # 七个阶段脚本，按课次顺序
├── mcp_server/math_server.py  # FastMCP 服务端（默认 stdio）
├── case/customer_service_agent.py  # 综合案例
├── logs/                      # 每个阶段的运行日志（验证证据）
├── requirements.txt
└── README.md
```

## 4. 运行方式

```powershell
# 1. 准备环境（Python 3.11）
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 2. 设置 key（当前会话有效）
$env:DEEPSEEK_API_KEY = "你的 key"

# 3. 让控制台按 UTF-8 解码，否则日志里的中文/emoji 会乱码或报 UnicodeEncodeError
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

# 4. 按顺序执行（在项目根目录）
python -m stages.s01_agent_basics
python -m stages.s02_models_messages
python -m stages.s03_streaming_structured
python -m stages.s04_tools_memory_guard
python -m stages.s05_mcp_hitl
python -m stages.s06_middleware_longmem
python -m stages.s07_multiagent
python -m case.customer_service_agent
```

## 5. 验证结果（日志见 `logs/`）

| 日志 | 关键证据 |
| --- | --- |
| `s01_agent_basics.log` | 工具返回 `128*0.85+12 = 120.8`；vip 报价 449、普通 499；`structured_response` 与文本一致 |
| `s02_models_messages.log` | 两条模型路径 token 用量一致；手写循环 2 轮工具调用后收敛；`AIMessageChunk` 相加为 `'LangChain'`；切 reasoner 后内容块为 `['reasoning','text']` |
| `s03_streaming_structured.log` | updates 出现 model→tools→model；messages 收到 13 个非空片段；custom 打出 3 条进度；列表模式产出 `(mode, chunk)`；纠错回调触发 1 次后成功输出 |
| `s04_tools_memory_guard.log` | 线程 B 仍读到长期偏好但不知道姓名；模型看到 `[REDACTED_EMAIL]` 与 `**** **** **** 1111`；api_key 抛 `PIIDetectionError`；违禁词场景模型调用次数 0 |
| `s05_mcp_hitl.log` | `get_tools()` 拿到 add/multiply，最终算出 294；中断时 `REFUND_CALLS=[]`，批准后为 `['A1001:268']`；拒绝分支新增记录为空 |
| `s06_middleware_longmem.log` | 工具第 1 次超时、第 2 次成功；5 字问题走 chat、49 字问题走 reasoner；换用户后提示词里的偏好和角色都变了 |
| `s07_multiagent.log` | 主管分别调用 presale_expert / aftersale_expert；入口路由 presale，最终 `active_agent=aftersale` |
| `case_customer_service.log` | 第 1 轮退款中断→批准→执行；第 2 轮写入 store；第 3 轮新会话调用 policy_expert；第 4 轮工单 `intent='售后'` |

## 6. 踩坑记录

1. **Python 版本**：LangChain 1.x 要求 ≥3.10，系统自带 3.8 直接不可用；本机用 3.11.9 建独立 venv，不污染全局。
2. **`stream_mode="updates"` 的产出形态**：单模式时每次产出就是 `{节点名: 数据}` 字典，不是 `(step, data)` 二元组；只有传 `["updates","custom"]` 列表时才变成 `(mode, chunk)`。课件按后者写，照抄前者会报 `not enough values to unpack`。
3. **工具返回 `Command` 时必须手动补 `ToolMessage`**：`tool_call_id=runtime.tool_call_id`，否则消息链缺一条 tool 消息，后续请求不合法。
4. **`PIIMiddleware("credit_card")` 会做 Luhn 校验**：随便编的卡号不会被 mask，要用 `4111 1111 1111 1111` 这类能通过校验的测试号。
5. **HITL 三件套**：`checkpointer` + 同一 `thread_id` + `Command(resume={"decisions":[...]})`。中断时工具确实没执行（日志里退款记录为空），批准后才写入。
6. **结构化输出纠错要用 `field_validator`**：像 `minimum/maximum` 这种约束会出现在 JSON Schema 里，模型提前避开就不会触发重试；自定义校验器的规则模型看不见，才是稳定的纠错演示。
7. **Windows 控制台编码**：模型回复里的 emoji 会让 GBK 控制台抛 `UnicodeEncodeError`，脚本里 `sys.stdout.reconfigure(encoding="utf-8")`；PowerShell 侧还要设 `[Console]::OutputEncoding`，否则 `Tee-Object` 存下来的日志是乱码。
8. **MCP stdio 日志走 stderr**：服务端的 `Processing request...` 打到 stderr，PowerShell 会显示成红色错误甚至让退出码为 1，但流程本身成功；看日志文件内容为准。
9. **LangGraph 交接的痕迹**：售前调用 transfer 工具后直接跳走，父图最终 state 里看不到那次 `tool_calls`，只能靠 `active_agent` 变化和回答内容判断交接成功。

## 7. 与课件的取舍

- **模型**：课件混用 DeepSeek 与 qwen-plus（含硬编码 key），这里统一 DeepSeek，key 只从环境变量读取，仓库内不含任何真实 key。
- **MCP 传输**：只跑 stdio（客户端拉起子进程、随用随停）；`streamable-http` 需要常驻 8000 端口，未在本目录启动，服务端留了 `--http` 参数可自行验证。
- **HITL 交互**：课件用 `input()` 人工确认，这里脚本化自动 approve/reject，便于无人值守复现。
- **持久化**：短期记忆用 `InMemorySaver`、长期记忆用 `InMemoryStore`，不依赖本地 MySQL；换数据库只需替换 checkpointer/store 实现。
- **多智能体入口路由**：课件用 LLM 判断，这里用关键词（退款/退货/物流/投诉）保证可复现；交接本身仍是课件式的 `Command(goto, graph=Command.PARENT)`。
- **版本**：课件 1.2.9、本机 1.4.9，用到的 `create_agent / system_prompt / context_schema / store / middleware / ToolRuntime / HumanInTheLoopMiddleware` 等符号全部实测存在。
