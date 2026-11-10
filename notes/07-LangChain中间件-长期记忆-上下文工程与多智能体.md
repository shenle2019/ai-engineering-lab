# LangChain 中间件、长期记忆、上下文工程与多智能体

> 来源：python 山顶会三期 day07（LangChain 高级组件之中间件 / 运行时 / 上下文工程 / 长期记忆等），课件 `day16-课堂笔记.md` + 代码包第 13–17 章
> 定位：理解向笔记，记录机制、要点与踩坑，不复刻课件代码

## 0. 这份内容在讲什么

day07 是 LangChain 单智能体部分的收口，讲的是「怎么把 Agent 变成一个可控、可维护、可分工的系统」：

```
中间件      → 控制执行流程的每个环节（重试、限流、拦截、动态换模型）
长期记忆    → 跨会话记住用户（store + namespace + key）
运行时      → 统一拿到 context / store / stream_writer
上下文工程  → Agent 不可靠的头号原因：上下文没给对
多智能体    → 一个 Agent 干不完时，拆成多个专业化 Agent 协作
RAG         → 补上模型不知道的外部知识（概念介绍）
```

一条主线可以串起来：**中间件是「控制手段」，长期记忆和运行时是「上下文来源」，上下文工程是「设计方法」，多智能体是「规模化结果」。**

## 1. 中间件（Middleware）

### 1.1 是什么

中间件提供精细控制 Agent 内部执行流程的方法。核心的 Agent 循环是：调用模型 → 模型选择并执行工具 → 不再调工具则结束。中间件在这些步骤的**前后**暴露钩子（hooks）。

四类能力：

| 能力 | 内容 |
| --- | --- |
| 监控 | 追踪行为：日志、分析、调试 |
| 修改 | 转换提示词、工具选择、输出格式 |
| 控制 | 添加重试、回退、提前终止 |
| 强制执行 | 速率限制、安全护栏、PII 检测 |

```python
agent = create_agent(
    model=model,
    tools=[...],
    middleware=[SummarizationMiddleware(), HumanInTheLoopMiddleware()],
)
```

day03 提过钩子，day06 用中间件做了护栏和 HITL，day07 才系统讲「中间件本身」。

### 1.2 内置中间件清单

这一批开箱即用，覆盖了绝大多数生产需求，没必要自己重写：

| 中间件 | 作用 |
| --- | --- |
| Summarization | 接近 token 上限时自动总结对话 |
| Human-in-the-loop | 暂停等待人工批准工具调用 |
| Model call limit | 限制模型调用次数，控成本 |
| Tool call limit | 限制工具调用次数 |
| Model fallback | 主模型失败时自动回落备用模型 |
| PII detection | 检测并处理个人身份信息 |
| To-do list | 给 Agent 任务规划与跟踪能力 |
| LLM tool selector | 调主模型前先用 LLM 挑选相关工具 |
| Tool retry | 工具调用失败按指数退避重试 |
| Model retry | 模型调用失败按指数退避重试 |
| LLM tool emulator | 用 LLM 模拟工具执行，用于测试 |
| Context editing | 修剪或清理工具调用占用的上下文 |
| Shell tool | 给 Agent 一个持久 shell 会话 |
| File search | 提供 Glob / Grep 文件搜索工具 |
| Filesystem | 给 Agent 文件系统，用于存上下文和长期记忆 |
| Subagent | 支持生成子 Agent |

值得注意 **LLM tool selector**：工具多到几十个时，模型的选错率会明显上升，先用一个小模型做筛选再交给主模型，是成本与准确率的折中。**Model fallback** 则是可用性保障的标配。

### 1.3 自定义中间件的两条路

| 方式 | 适用 |
| --- | --- |
| 装饰器（Decorator-based） | 单钩子中间件，快速简单 |
| 类（Class-based） | 多钩子的复杂中间件，能力更强 |

### 1.4 六种钩子 + 一个便利装饰器

**节点式（Node-style）——在特定执行点顺序运行**

| 钩子 | 时机 |
| --- | --- |
| `@before_agent` | Agent 启动前，每次调用一次 |
| `@before_model` | 每次模型调用前 |
| `@after_model` | 每次模型响应后 |
| `@after_agent` | Agent 完成时，每次调用最多一次 |

**包装式（Wrap-style）——拦截并控制执行**

| 钩子 | 时机 |
| --- | --- |
| `@wrap_model_call` | 每次模型调用周围 |
| `@wrap_tool_call` | 每次工具调用周围 |

**便利装饰器**

| 装饰器 | 等价于 |
| --- | --- |
| `@dynamic_prompt` | 修改提示词的 `@wrap_model_call` |

节点式适合日志、校验、状态更新；包装式适合重试、缓存、转换——因为包装式能决定 handler **调 0 次（短路）、1 次（正常）还是多次（重试）**。

### 1.5 装饰器写法：四个典型钩子

```python
@before_model
def log_before_model(state: AgentState, runtime: Runtime) -> dict | None:
    print(f"About to call model with {len(state['messages'])} messages")
    return None

@after_model(can_jump_to=["end"])
def validate_output(state: AgentState, runtime: Runtime) -> dict | None:
    last_message = state["messages"][-1]
    if "BLOCKED" in last_message.content:
        return {"messages": [AIMessage("I cannot respond to that request.")], "jump_to": "end"}
    return None

@wrap_model_call
def retry_model(request: ModelRequest, handler: Callable[[ModelRequest], ModelResponse]) -> ModelResponse:
    for attempt in range(3):
        try:
            return handler(request)
        except Exception:
            if attempt == 2:
                raise

@dynamic_prompt
def personalized_prompt(request: ModelRequest) -> str:
    user_name = request.runtime.context.get("user_name", "guest")
    return f"You are a helpful assistant for user {user_name}."
```

三个语法细节：

1. **节点式钩子返回 `dict | None`**：`None` 表示不干预，`dict` 表示更新状态。
2. **`jump_to: "end"` 需要声明**：装饰器上写 `@after_model(can_jump_to=["end"])`，或用 `@hook_config(can_jump_to=["end"])`。不声明就跳不了。
3. **包装式钩子必须调用 `handler(request)`**：不调就是短路（模型根本不会被调用），调多次就是重试。

### 1.6 类写法：多钩子组合

```python
class LoggingMiddleware(AgentMiddleware):
    def before_model(self, state, runtime): ...
    def after_model(self, state, runtime): ...

class MessageLimitMiddleware(AgentMiddleware):
    def __init__(self, max_messages: int = 50):
        super().__init__()                     # 必须调父类初始化
        self.max_messages = max_messages

    def before_model(self, state, runtime):
        if len(state["messages"]) >= self.max_messages:
            return {"messages": [AIMessage("Conversation limit reached.")], "jump_to": "end"}
        return None

class RetryMiddleware(AgentMiddleware):
    def wrap_model_call(self, request, handler):
        for attempt in range(self.max_retries):
            try:
                return handler(request)
            except Exception:
                if attempt == self.max_retries - 1:
                    raise
```

**`super().__init__()` 不能省**——父类初始化要完成中间件注册等工作，漏了会出现难以定位的异常。这是类式中间件最常见的错误。

### 1.7 动态模型：`request.override`

```python
class DynamicModelMiddleware(AgentMiddleware):
    def wrap_model_call(self, request, handler):
        model = qian_wen if random.choice([True, False]) else deep_seek
        return handler(request.override(model=model))
```

`request.override(model=...)` 是「临时替换本次调用的模型」，不改 Agent 的默认模型。这是实现**按难度选模型、按成本降级、A/B 测试**的标准手法。

课件在这里埋了一个很真实的注释：随机切到 DeepSeek 时，那个 key 已失效，请求直接失败，结果被 `RetryMiddleware` 兜住，重试时随机到了千问，就通了。**这说明两件事**：动态换模型必须有重试兜底；线上任何一个模型都可能挂，fallback 不是可选项。

### 1.8 中间件的叠加顺序

`middleware=[A(), B(), C()]` 按列表顺序叠加。这个顺序会实质影响行为：`LoggingMiddleware` 放在 `RetryMiddleware` 外层还是内层，日志里记录的是「一次逻辑调用」还是「每次物理重试」，完全不同。设计中间件链时要先想清楚这个顺序。

## 2. 长期记忆（Long-term memory）

### 2.1 与短期记忆的分界

| | 短期记忆 | 长期记忆 |
| --- | --- | --- |
| 载体 | LangGraph checkpointer | LangGraph store |
| 作用域 | 单个 thread（一次会话） | 跨会话、跨线程 |
| 内容 | 消息历史 + 自定义 state 字段 | 任意 JSON 文档（用户偏好、知识） |
| 失效 | 换 thread_id 就没了 | 一直存在，直到显式删除 |

一句话：**短期记忆是「这场对话里说过什么」，长期记忆是「这个用户是谁」。**

### 2.2 数据结构：namespace + key

LangGraph 把长期记忆作为 JSON 文档存在 store 里：

```
namespace（类似文件夹，元组）  +  key（类似文件名）  →  JSON 文档
例：("users",) + "user_123" → {"name": "lqz", "language": "English"}
```

namespace 通常包含用户 ID、组织 ID 或其他标签，因此天然支持**层次化组织**和跨命名空间搜索。

```python
from langgraph.store.memory import InMemoryStore

def embed(texts: list[str]) -> list[list[float]]:
    return [[1.0, 2.0] * len(texts)]        # 占位，实际用真嵌入模型

store = InMemoryStore(index={"embed": embed, "dims": 2})

store.put(("my-user", "chitchat"), "a-memory", {
    "rules": ["User likes short, direct language", "User only speaks English & python"],
})

item = store.get(("my-user", "chitchat"), "a-memory")
items = store.search(("my-user", "chitchat"), filter={"my-key": "my-value"}, query="language preferences")
```

三个 API 要掌握：`put`（写）、`get`（按 key 取）、`search`（按过滤条件 + 向量相似度搜）。`search` 的 `query` 需要 store 配了 `embed` 才能做语义检索。

`InMemoryStore` 只存内存，**进程重启即失**；生产要用基于数据库的实现。

### 2.3 在工具里读写长期记忆

写入：

```python
@tool
def save_user_info(user_info: UserInfo, runtime: ToolRuntime[Context]) -> str:
    """Save user info."""
    store = runtime.store                       # 与 create_agent 传入的是同一个
    user_id = runtime.context.user_id           # 用户身份来自 context
    store.put(("users",), user_id, user_info)
    return "Successfully saved user info."

agent = create_agent(model, tools=[save_user_info], store=store, context_schema=Context)
agent.invoke({"messages": [...]}, context=Context(user_id="user_123"))
```

读取：

```python
@tool
def get_user_info(runtime: ToolRuntime[Context]) -> str:
    """Look up user info."""
    user_info = runtime.store.get(("users",), runtime.context.user_id)
    return str(user_info.value) if user_info else "Unknown user"
```

这里体现了一个很重要的设计思路：**工具不需要用户 id 参数**。模型不知道「当前是谁」，也不需要知道；身份从 `context` 注入，工具自己拼 `namespace + key` 去查。这既减少了模型的出错面，又避免了「用户 A 问到用户 B 的数据」这类越权。

**`store.get()` 返回的是 `StoreValue` 对象，真实数据在 `.value` 里**。直接当字典用会出错，这是必踩的一脚。

## 3. 运行时（Runtime）

### 3.1 三件套

`create_agent` 实际跑在 LangGraph 运行时上，`Runtime` 对象包含：

| 成员 | 内容 |
| --- | --- |
| `context` | 静态信息：用户 ID、数据库连接、调用所需依赖 |
| `store` | 长期记忆实例 |
| `stream_writer` | 通过 `custom` 流模式发消息的对象 |

### 3.2 声明与传值

```python
@dataclass
class Context:
    user_name: str

agent = create_agent(model, tools=[fetch_user_name], middleware=[log_before_model], context_schema=Context)
agent.invoke({"messages": [...]}, context=Context(user_name="lqz"))
```

`context_schema` 声明类型，`invoke(context=...)` 传值。类型可以是 `@dataclass`、`TypedDict`、Pydantic 模型。

### 3.3 三处访问点

```python
# 1 工具里
@tool
def fetch_user_name(runtime: ToolRuntime[Context]) -> str:
    """获取用户姓名."""
    return runtime.context.user_name

# 2 中间件里
@before_model
def log_before_model(state: AgentState, runtime: Runtime[Context]) -> dict | None:
    print(f"Processing request for user: {runtime.context.user_name}")
    return None

# 3 动态提示词里
@dynamic_prompt
def p(request: ModelRequest) -> str:
    return f"User: {request.runtime.context.user_name}"
```

三处的类型标注不同（`ToolRuntime[Context]` / `Runtime[Context]` / `request.runtime.context`），这是最常见的记混点。规律是：**在工具里用 ToolRuntime，在图/中间件里用 Runtime，在 prompt 里从 request 上取。**

## 4. 上下文工程（Context Engineering）

### 4.1 核心论断

课件开头给了两个原因解释「Agent 为什么会失败」：

1. 底层 LLM 能力不足
2. 没有把「正确的」上下文传给 LLM

**结论是：Agent 不可靠的首要原因通常是第二个。** 上下文工程就是「以正确的格式提供正确的信息和工具」，被定义为「AI 工程师的头号工作」。

这个判断很值得记住。很多「模型不行」的抱怨，实际是提示词缺约束、历史没带上、工具描述不清楚、状态字段没传——全是上下文问题。

### 4.2 上下文的三类来源

课件强调：**上下文工程 ≠ LangChain 的 `context` 对象**。它是一个更大的概念，包含三类载体：

| 来源 | 内容 |
| --- | --- |
| 短期记忆 | 本次会话的消息历史 + 自定义 state 字段 |
| 长期记忆 | store 里的用户偏好、历史事实 |
| 运行时上下文 | 本次调用的身份、角色、环境等配置 |

一个很精炼的表述：**上下文大于提示词，因为上下文包含历史**。提示词只是上下文的一部分。

课件还顺手给了两个观点：`function calling 包含 mcp`（协议在机制之上，不是替代）；`skills 本质是一堆预置提示词`（用统一规范约束模型输出，避免每次生成风格不一）。

### 4.3 三个典型手法

**手法一：按对话长度调整策略**

```python
@dynamic_prompt
def state_aware_prompt(request: ModelRequest) -> str:
    message_count = len(request.messages)     # request.messages 是 request.state["messages"] 的快捷方式
    base = "You are a helpful assistant."
    if message_count > 10:
        base += "\nThis is a long conversation - be extra concise."
    return base
```

**手法二：从长期记忆注入用户偏好**

```python
@dynamic_prompt
def store_aware_prompt(request: ModelRequest) -> str:
    user_id = request.runtime.context.user_id
    user_prefs = request.runtime.store.get(("preferences",), user_id)
    base = "You are a helpful assistant."
    if user_prefs:
        base += f"\nUser prefers {user_prefs.value.get('communication_style', 'balanced')} responses."
    return base
```

**手法三：按角色和环境收紧权限**

```python
@dynamic_prompt
def context_aware_prompt(request: ModelRequest) -> str:
    role = request.runtime.context.user_role
    env = request.runtime.context.deployment_env
    if role == "admin":
        base += "\nYou have admin access."
    elif role == "viewer":
        base += "\nYou have read-only access."
    if env == "production":
        base += "\nBe extra careful with any data modifications."
    return base
```

三个手法的共同点：**提示词不是写死的常量，而是每次调用前根据状态动态拼出来的**。这就是 `@dynamic_prompt` 存在的意义——它比写在 `system_prompt` 里的静态文本强得多，因为后者对所有人、所有阶段都一样。

## 5. 多智能体（Multi-agent）

### 5.1 什么时候需要拆

单个 Agent 撑不住时，才拆：

- 工具太多，模型难以决定用哪个
- 上下文或记忆对单个 Agent 来说过于庞大
- 任务需要专业化分工（规划者、研究员、数学专家）

课件给的例子很直观——「一键生成历史人物讲解视频」：文本 Agent 写描述 → 工具转语音 → 视频 Agent 生成 → 输出。一条流水线，每段是专业化的。

### 5.2 做法一：Agent 当工具（最简单）

把一个 Agent 包成 `@tool`，让另一个 Agent 去调：

```python
agent01 = create_agent(model=model01)          # 医疗专家

@tool("agent01", description="医疗专家")
def doctor(query: str):
    result = agent01.invoke({"messages": [{"role": "user", "content": query}]})
    return result["messages"][-1].content

agent02 = create_agent(model=model2, tools=[doctor])   # 主控
agent02.invoke({"messages": [{"role": "user", "content": "血压80/150正常吗?"}]})
```

外部触发的是 `agent02`，但实际回答来自 `agent01`——**选择权在模型手里，它认为需要专家就调 `doctor`**。

优点：实现极简，几乎不用学新东西。缺点：子 Agent 变成黑盒，中间过程不可观测、不可路由、不能来回交接。

### 5.3 做法二：LangGraph 图 + Command 交接

需要「双向转接」时（销售转技术支持、技术支持再转回销售），要用 LangGraph 显式建图。

**第 1 步：状态里记录当前活跃 Agent**

```python
class MultiAgentState(AgentState):
    active_agent: NotRequired[str]
```

**第 2 步：把「转接」做成工具，返回 Command**

```python
@tool
def transfer_to_support(runtime: ToolRuntime) -> Command:
    """Transfer to the support agent."""
    last_ai_message = next(m for m in reversed(runtime.state["messages"]) if isinstance(m, AIMessage))
    transfer_message = ToolMessage(
        content="Transferred to support agent from sales agent",
        tool_call_id=runtime.tool_call_id,
    )
    return Command(
        goto="support_agent",
        update={"active_agent": "support_agent", "messages": [last_ai_message, transfer_message]},
        graph=Command.PARENT,
    )
```

三个细节都不能漏：

1. **`goto="support_agent"`** 指定跳转到哪个节点。
2. **`graph=Command.PARENT`** 表示跳到父图。子图里的 Command 默认只在子图内跳，跨图必须显式声明 PARENT。
3. **`update` 里要带上 `last_ai_message`**。原来的 AIMessage（含 tool_calls）必须一起写回状态，否则消息链断掉——tool_calls 后面没有对应的 tool 结果，请求会报错。

**第 3 步：路由函数**

```python
def route_initial(state) -> Literal["sales_agent", "support_agent"]:
    return state.get("active_agent") or "sales_agent"

def route_after_agent(state) -> Literal["sales_agent", "support_agent", "__end__"]:
    messages = state.get("messages", [])
    if messages:
        last_msg = messages[-1]
        if isinstance(last_msg, AIMessage) and not last_msg.tool_calls:
            return "__end__"                       # 没有工具调用 = 任务完成
    return state.get("active_agent", "sales_agent")
```

**终止条件是多智能体最容易写错的地方**：如果 `route_after_agent` 无脑返回 `active_agent`，两个 Agent 会互相转接直到步数耗尽。判据用「最后一条 AIMessage 且无 tool_calls」——这意味着模型已经给出最终回答，可以结束了。

**第 4 步：建图**

```python
builder = StateGraph(MultiAgentState)
builder.add_node("sales_agent", call_sales_agent)
builder.add_node("support_agent", call_support_agent)
builder.add_conditional_edges(START, route_initial, ["sales_agent", "support_agent"])
builder.add_conditional_edges("sales_agent", route_after_agent, ["sales_agent", "support_agent", END])
builder.add_conditional_edges("support_agent", route_after_agent, ["sales_agent", "support_agent", END])
graph = builder.compile()
```

### 5.4 两种做法怎么选

| | Agent 当工具 | LangGraph 图 |
| --- | --- | --- |
| 实现成本 | 极低 | 中（要懂 LangGraph） |
| 流向 | 单向（主控 → 专家） | 双向，可任意转接 |
| 可观测 | 差（黑盒） | 好（每个节点可见） |
| 适用 | 简单分工、专家咨询 | 客服转接、复杂流水线 |

## 6. RAG（检索增强生成）

课件只讲了概念，没展开实现，但动机要记住：

- **有限的上下文**：模型无法一次消化整个语料库
- **静态的知识**：训练数据固定在某个时间点，公司新规章它不可能知道

RAG 的做法是「检索 + 生成」：查询时先从外部知识库取出相关片段，拼进上下文再让模型回答。

典型场景：问「公司规章第三条是什么」，模型本来答不出，接上 RAG 后能准确回答。区别在于——**RAG 不是把知识训进模型，而是每次问答时临时把知识塞进上下文**。这也是它比微调更常用的原因：知识更新只需换文档，不用重训模型。

## 7. 踩坑清单

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| 类式中间件报莫名错误 | `__init__` 没调 `super().__init__()` | 补上父类初始化 |
| `jump_to` 无效 | 没声明 `can_jump_to` | 装饰器上加 `can_jump_to=["end"]` 或 `@hook_config` |
| 重试中间件没生效 | `wrap_model_call` 里没调 `handler(request)` | 包装式必须调用 handler 才会真正执行 |
| 日志次数比预期多 | 中间件顺序：重试在外层，日志在内层 | 调整 `middleware` 列表顺序 |
| 动态换模型频繁失败 | 某个模型 key 失效/服务不可用 | 必须配 Retry / ModelFallback 中间件 |
| 长期记忆取不到数据 | `store.get()` 返回 `StoreValue`，被当字典用 | 取 `.value` |
| 重启后长期记忆全没了 | 用的是 `InMemoryStore` | 生产换数据库实现 |
| `store.put` 报 key 类型错误 | key 用了 list/dict 等可变类型 | namespace 用元组、key 用不可变类型 |
| 工具拿不到用户身份 | 没配 `context_schema` 或 invoke 没传 `context` | 两处配套 |
| 多智能体死循环 | 路由函数缺终止条件 | 加「最后一条 AIMessage 无 tool_calls → END」 |
| 转接后请求报消息结构错误 | `Command.update` 漏了 `last_ai_message` | 把原 AIMessage 一起写回状态 |
| 子图里的 Command 跳不动 | 没加 `graph=Command.PARENT` | 跨图跳转必须显式声明 |
| 动态提示词取不到 store | `create_agent` 没传 `store=` | store 也要注入 |

## 8. 关键知识清单（速查）

**中间件**

- 定位：控制 Agent 每一步；四类能力：监控 / 修改 / 控制 / 强制执行
- 内置 16 个，重点是 Summarization、HITL、Model/Tool Call Limit、Model Fallback、PII、Tool Selector、Retry、Context Editing、Subagent
- 两种写法：装饰器（单钩子）/ 类（多钩子，`__init__` 必须 `super().__init__()`）
- 六个钩子：`before_agent` / `before_model` / `after_model` / `after_agent` + `wrap_model_call` / `wrap_tool_call`
- 便利装饰器：`@dynamic_prompt`
- 节点式返回 `dict | None`；`jump_to: "end"` 需 `can_jump_to` 声明
- 包装式决定 handler 调 0 次（短路）/ 1 次 / 多次（重试）
- 动态换模型：`handler(request.override(model=...))`
- 叠加顺序 = `middleware` 列表顺序，会实质影响行为

**长期记忆**

- 载体：LangGraph store；结构：`namespace`（元组）+ `key` → JSON 文档
- API：`put` / `get`（取 `.value`）/ `search`（filter + 向量 query）
- `InMemoryStore` 可配 `index={"embed":..., "dims":...}`；生产用数据库实现
- 工具内通过 `runtime.store` + `runtime.context.user_id` 定位用户

**运行时**

- 三件套：`context`（静态配置）/ `store`（长期记忆）/ `stream_writer`（custom 流）
- 声明 `context_schema`，调用 `invoke(context=...)`
- 访问点：工具 `ToolRuntime[Context]` / 中间件 `Runtime[Context]` / prompt `request.runtime.context`

**上下文工程**

- Agent 失败首因：上下文没给对，不是模型不行
- 三类来源：短期记忆 / 长期记忆 / 运行时上下文
- 「上下文大于提示词」，包含历史
- 三种手法：按消息条数调策略 / 从 store 注入偏好 / 按角色与环境收紧权限

**多智能体**

- 拆分时机：工具过多、上下文过大、需要专业化
- 做法一：Agent 包成 `@tool`（简单、单向、黑盒）
- 做法二：LangGraph 图 + `Command(goto=..., update={active_agent, messages}, graph=Command.PARENT)`
- 路由必须有终止条件：最后一条 AIMessage 无 `tool_calls` → END
- 转接时 `update` 必须带上原 `AIMessage`，保持消息链合法

**RAG**

- 动机：上下文有限 + 知识静态
- 做法：检索外部知识拼进上下文，而非把知识训进模型
- 知识更新只需换文档，不用重训
