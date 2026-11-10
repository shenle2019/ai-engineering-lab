# LangChain 框架概览与 Agents 智能体入门

> 来源：python 山顶会三期 day03（LangChain v1.2.9 核心组件之 Agents 和 Models），课件 `day12-课堂笔记.md` + 代码包第 1–3 章
> 定位：理解向笔记，记录机制、要点与踩坑，不复刻课件代码；代码只给最小可辨认的配置片段

## 0. 这份内容在讲什么

day03 是 LangChain 的第一课，主线是「从一个模型调用，长成一个会自己用工具的智能体」：

```
LangChain 是什么 / 谁的生态
   │
   ▼
装好环境，先用最直接的方式调一次模型（ChatOpenAI.invoke）
   │
   ▼
create_agent(model, tools, system_prompt)   ← 三要素
   │  模型怎么给（字符串 / 对象）、工具怎么写（@tool）、提示词怎么给（静态 / 动态）
   ▼
agent.invoke({"messages": [...]})  ← 拿到状态字典
   │
   ▼
高级概念速览：结构化输出（两策略）、短期记忆（自定义 state）、流式（values）
   │
   ▼
中间件钩子（下一课展开）
```

day03 的价值不在代码量，而在于把 LangChain 1.x 的**统一入口**建立起来：老版本有几十种 `create_xxx_agent`，1.x 只保留 `create_agent` 一个，其余能力全部通过参数和中间件挂上去。理解了这一点，后面 day04–day07 都是往这个入口上挂东西。

## 1. LangChain 是什么

### 1.1 一句话定位

LangChain 是构建**基于大语言模型的应用**的开源框架，核心价值是把 LLM 和外部数据、工具、业务逻辑接起来。它不是一个库，而是一个模块化生态，业内叫「LangChain 家族」。

关键认知：**LangChain 的 Agent 建立在 LangGraph 之上**，持久执行、流式、人工参与、状态持久化这些能力都是从 LangGraph 来的。做单智能体不需要了解 LangGraph，做多智能体再去看也不迟。

### 1.2 发展史中值得记住的几个节点

| 时间 | 事件 | 为什么值得记 |
| --- | --- | --- |
| 2022.11 | 项目诞生，几百行 demo | 核心概念是 Chain（链式调用）+ PromptTemplate |
| 2023.03 | v0.1.0 首个稳定版 | 模块化雏形：Chains / Memory / 工具调用雏形 |
| 2023 中–2024 初 | v0.2.x–v0.3.x 生态扩张 | 引入 Agent 抽象与自定义工具，问题也集中暴露 |
| 2024 | 模块化重构 | 拆 monorepo：core / community / 独立厂商包 |
| 2025.09 | 1.0 Alpha | 统一 `create_agent()`，引入 Middleware，深度整合 LangGraph |
| 2025.10.23 | 1.0 正式发布 | 从「原型工具」转向「生产就绪框架」 |

0.2–0.3 时代暴露的三个问题，正是 1.0 要解决的：**API 不统一**（几十种 `create_xxx_agent`）、**包体积臃肿**（全量安装）、**抽象过重导致定制困难**。所以看到 1.x 只有 `create_agent` 一个入口，是刻意的收敛，不是功能缩水。

版本节奏：1.2.x 几乎一周一个版本，改 bug 为主，1.2 到 1.3 无本质差距；但 **0.3.x 到 1.x 是有断层差距的**（类似 Python 2 到 3）。学习期固定 1.2.9，避免追新踩到 API 漂移。

### 1.3 家族七件套与选型

| 组件 | 作用 | 是否必须 |
| --- | --- | --- |
| `langchain-core` | 基础抽象与接口（LLM、ChatModel、Tool、Document、Retriever） | 装主包时自动带上 |
| `langchain` | 主包：Chains、Agents、Retrieval、Memory、Callbacks | 必须 |
| `langchain-community` | 社区集成：向量库、文档加载器、部分厂商适配 | 按需 |
| `langchain-openai` / `-deepseek` / `-ollama` / `-anthropic` | 独立厂商包 | 按需 |
| `langgraph` | 有状态、多参与者、循环控制流的工作流 | 高级场景 |
| `langserve` | 把 Chain/Runnable 部署成 REST API | 要部署时 |
| `LangSmith` | 追踪、评测、监控平台（SaaS，收费） | 可选，企业常因收费与数据安全不用 |
| `DeepAgents` | 面向单智能体开发的新产品 | 了解即可 |

分工的演化方向值得注意：官方想把「LangChain = 框架」这个历史印象淡化，变成「LangChain = 整个生态」。未来的分工预期是单智能体用 DeepAgents、多智能体用 LangGraph、监控用 LangSmith、部署用 LangServe。

## 2. 环境与第一次调用

### 2.1 安装

```bash
pip install langchain langchain-openai python-dotenv
# 需要官方包时再补
pip install langchain-deepseek langchain-ollama langchain-anthropic
```

要求 Python ≥ 3.10（1.x 官方要求），课件用 3.13，本仓库实操用 3.11.9。验证方式就是打印版本号：

```python
import langchain
print(langchain.__version__)   # 期望 1.2.9
```

### 2.2 直接调模型

```python
from langchain_openai import ChatOpenAI
llm = ChatOpenAI(model=..., api_key=..., base_url=...)
llm.invoke("介绍一下自己？")
```

这一步只是证明「LangChain 能接上模型」，还没有 Agent。凭据一律走 `.env` + `os.getenv`，不要把 key 写进源码——课件里大量直接内联 `sk-` 开头的 key，这是讲课方便，工程上不能这么干。

课件准备了两个 `.env`：一个指向本地 ollama（`qwen3-vl:2b`），一个指向远程 DeepSeek，切换靠 `load_dotenv()` 的文件名。这个做法很实用：本地模型验证链路，远程模型验证真实能力。

## 3. create_agent：智能体的三要素

### 3.1 心智模型

```python
from langchain.agents import create_agent

agent = create_agent(
    model=...,            # 推理引擎
    tools=[...],          # 能动的外部能力
    system_prompt="...",  # 行为约束
)
```

Agent 的运行是一个**循环**：模型思考 → 决定调哪个工具 → LangChain 自动执行工具 → 结果回填 → 模型再思考 → 直到模型不再调用工具（产出最终回答）或达到迭代上限。

与 day01 手写 Function Calling 的对比，是理解 Agent 价值的最快方式：

| | 裸 Model 调工具 | Agent 调工具 |
| --- | --- | --- |
| 工具注册 | `model.bind_tools([...])` 手写 JSON Schema | `@tool` 装饰器，schema 自动生成 |
| 工具执行 | 自己写映射表、自己调函数 | LangChain 自动执行 |
| 结果回填 | 自己 append `role=tool` 消息 | 自动 append `ToolMessage` |
| 循环控制 | 自己写 while + 最大步数 | 内置循环，自动判断停止 |

day03 的结论可以浓缩成一句：**Agent 把 Function Calling 的七步流程封进了框架，开发者只需要给模型、给工具、给约束。**

### 3.2 模型怎么给：字符串 vs 对象

这是 day03 最容易踩坑的地方，两种写法差别很大。

**写法一：字符串（省事，但配置受限）**

```python
agent = create_agent(model="deepseek:deepseek-chat")   # 官方独立接口，需 langchain-deepseek
agent = create_agent(model="openai:deepseek-chat")     # OpenAI 兼容接口，需 langchain-openai
```

字符串格式是 `provider:model`，provider 必须是已安装的集成。模型名支持写成固定集合中的值。

**关键限制：`create_agent` 没有 `api_key` / `base_url` 参数**，传了会报错。凭据必须走环境变量：

```python
import os
os.environ["DEEPSEEK_API_KEY"] = "..."     # 注意变量名随 provider 变化
# langchain-deepseek 内置了 base_url，不用额外设
```

**写法二：模型对象（推荐，可控）**

```python
from langchain_openai import ChatOpenAI
model = ChatOpenAI(model="deepseek-chat", api_key=..., base_url=..., temperature=0.1, max_tokens=..., timeout=...)
agent = create_agent(model=model)
```

传对象能控制 `temperature`、`max_tokens`、`timeout` 等参数，还能在同一个 Agent 里做动态切换。**只要不是简单 demo，一律传对象。**

### 3.3 工具怎么写：@tool 与 docstring

```python
from langchain.tools import tool

@tool
def get_weather(city: str) -> str:
    """获取给定城市的天气。"""
    return f"{city} 晴"
```

三条硬规则：

1. **docstring 是给模型看的说明书**，不是注释。没有 docstring，模型不知道什么时候该调它。
2. **类型注解是必需的**，它决定工具的参数 schema。
3. 工具函数返回的字符串会作为 `ToolMessage` 回填给模型，所以返回内容要让模型能直接读懂。

### 3.4 提示词怎么给：静态与动态

**静态**：`system_prompt="你是一个..."`，一次写死。

**动态**：需要按用户身份、时间、外部状态变化时，用 `@dynamic_prompt` 中间件：

```python
@dynamic_prompt
def dynamic_system_prompt(request: ModelRequest) -> str:
    user_name = request.runtime.context["user_name"]
    return f"你是一个助手，请称呼用户为 {user_name}。"

agent = create_agent(model, middleware=[dynamic_system_prompt], context_schema=Context)
agent.invoke({...}, context=Context(user_name="张三"))
```

动态提示词和三样东西绑定：`@dynamic_prompt` 装饰器、`context_schema` 声明上下文类型、`invoke(context=...)` 传值。三者缺一，`request.runtime.context` 就取不到东西。

### 3.5 调用与返回

```python
result = agent.invoke({"messages": [{"role": "user", "content": "..."}]})
result["messages"][-1].content      # 最终回答
result["messages"]                  # 完整对话（含工具调用与结果）
result["structured_response"]       # 仅在配置了 response_format 时存在
```

返回的是一个**状态字典**，不是单纯的字符串。理解这一点很关键：Agent 的一次 invoke 里包含多轮消息，`messages[-1]` 只是最后一轮。

## 4. 高级概念速览（day03 只到「会用」）

### 4.1 结构化输出两策略

```python
from langchain.agents.structured_output import ToolStrategy, ProviderStrategy

agent = create_agent(model=model, response_format=ToolStrategy(ContactInfo))    # 兜底方案
agent = create_agent(model=model, response_format=ProviderStrategy(ContactInfo)) # 需模型原生支持
agent = create_agent(model=model, response_format=ContactInfo)                  # 自动选择
result["structured_response"]
```

| | ToolStrategy | ProviderStrategy |
| --- | --- | --- |
| 原理 | LangChain 内部注册一个「结构化输出工具」，让模型以工具调用形式返回，再解析成对象 | 直接用供应商的原生结构化输出能力 |
| 适用范围 | 所有支持工具调用的模型 | 仅原生支持的供应商（OpenAI、qwen-plus 等） |
| 代价 | 多一轮工具调用，更耗资源 | 更直接、更可靠 |
| DeepSeek | 可用 | 报 `this response_format type is unavailable now` |

直接传 Schema 类型时，LangChain 会按模型能力自动选：支持原生的用 ProviderStrategy，否则退回 ToolStrategy。**想跨厂商稳，就显式写 ToolStrategy。**

### 4.2 短期记忆：自定义 state 的两种方式

目标是在对话过程中记住 `messages` 之外的额外信息（比如用户偏好）。

**方式一：中间件（推荐）**

```python
class CustomState(AgentState):
    user_preferences: dict

class CustomMiddleware(AgentMiddleware):
    state_schema = CustomState
    def before_model(self, state: CustomState, runtime):
        print(state.get("user_preferences"))

agent = create_agent(model, middleware=[CustomMiddleware()])
agent.invoke({"messages": [...], "user_preferences": {"username": "lqz"}})
```

**方式二：`create_agent(state_schema=...)`**

状态变成全局的，工具里通过 `ToolRuntime.state` 访问。

推荐中间件方式的原因：状态扩展被**限定在相关中间件和工具的范围内**，不会污染整个 Agent 的状态契约。这一点在项目变大后差别很明显。

### 4.3 流式：values 模式

```python
for chunk in agent.stream({"messages": [...]}, stream_mode="values"):
    latest = chunk["messages"][-1]
    if latest.content:
        print(latest.content)
    elif latest.tool_calls:
        print([tc["name"] for tc in latest.tool_calls])
```

`values` 每次给出的是**该时刻的完整状态快照**，所以要取 `messages[-1]`。想按节点拿增量、按 token 拿输出，是 day05 的内容。

### 4.4 中间件钩子（预告）

```python
@before_model    # 每次模型调用前
@after_model     # 每次模型响应后
@wrap_tool_call  # 每次工具调用周围
```

day03 只演示了打印和取状态。真正的能力（改写提示词、动态换模型、重试、护栏、人机审批）在 day06–day07 展开。

## 5. 踩坑清单

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| `create_agent` 传 `api_key` 报错 | 该函数刻意不接收凭据参数 | 用 `os.environ["XXX_API_KEY"]`，变量名随 provider 变 |
| 模型字符串连不上 | `provider:model` 的 provider 没装对应包 | `deepseek:` 装 `langchain-deepseek`，`openai:` 装 `langchain-openai` |
| 模型从不调用工具 | 工具缺 docstring，或描述太含糊 | docstring 写清「做什么、什么场景用」 |
| `ProviderStrategy` 报 unavailable | 该模型不支持原生结构化输出（如 DeepSeek） | 换 `ToolStrategy`，或改直传 Schema 让它自动降级 |
| 动态提示词取不到 `context` | 缺 `context_schema` 或 invoke 没传 `context` | 三者要配套：装饰器 + schema + invoke 参数 |
| `state_schema` 的字段拿不到 | invoke 时没把自定义字段一起传 | `{"messages": [...], "user_preferences": {...}}` |
| 版本对不上 | 0.3.x 与 1.x 是断层差距 | 固定 1.2.9，别照抄 0.3 时代的老教程 |

## 6. 关键知识清单（速查）

- LangChain 1.x 只有一个 Agent 入口：`create_agent(model, tools, system_prompt)`
- Agent = 模型 + 工具 + 提示词，运行是「模型 → 工具 → 模型」的循环，直到模型不再调工具
- Agent 建立在 LangGraph 之上；单智能体不需要学 LangGraph
- 装包：`langchain` + 厂商包（`langchain-openai` 最通用）+ `python-dotenv`
- 模型给法两种：字符串（`provider:model`，凭据走环境变量）/ 对象（可控参数，推荐）
- `create_agent` 没有 `api_key`、`base_url` 参数
- `@tool` + docstring + 类型注解 = 一份完整的工具说明书
- 提示词：`system_prompt` 静态 / `@dynamic_prompt` 动态（配 `context_schema` + `invoke(context=)`）
- 返回状态字典：`messages` 是完整对话，`structured_response` 只在配了 `response_format` 时存在
- 结构化输出：`ToolStrategy` 通用兜底，`ProviderStrategy` 需供应商原生支持
- 短期记忆自定义状态：中间件 `state_schema`（推荐）> `create_agent(state_schema=)`
- 流式先记 `stream_mode="values"`（整状态快照），其余模式看 day05
- 中间件三件套预告：`@before_model` / `@after_model` / `@wrap_tool_call`
