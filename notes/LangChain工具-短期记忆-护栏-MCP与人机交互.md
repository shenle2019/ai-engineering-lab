# LangChain 工具、短期记忆、护栏、MCP 与人机交互

> 来源：python 山顶会三期 day06（LangChain 高级组件之工具 / 短期记忆 / 护栏 / MCP / 人机交互），课件 `day15-课堂笔记.md` + 代码包第 8–12 章
> 定位：理解向笔记，记录机制、要点与踩坑，不复刻课件代码

## 0. 这份内容在讲什么

day06 回答一个很现实的问题：**Agent 从 demo 走向生产，缺的是什么。**

```
给能力  → 工具（Tools）：让模型能动手，且能拿到运行时信息
给记忆  → 短期记忆（Short-term memory）：让同一会话内的上下文不断线
给边界  → 护栏（Guardrails）：不该回答的、不该泄露的，在调用模型前就拦住
给生态  → MCP：把第三方工具直接挂上来，不用自己写
给控制  → 人机交互（HITL）：危险操作必须有人点头
```

五个能力对应五个典型的生产问题：能力不足、上下文丢失、合规风险、工具重复造、误操作不可控。

## 1. 工具（Tools）

### 1.1 工具的定位

工具是 Agent 调用来执行操作的组件，封装「一个可调用函数 + 输入 schema」。它扩展了模型的能力边界：模型本身不能联网、不知道实时消息、读不到公司内部规章，这些都靠工具补。

两种调用路径要分清：

| | 裸 Model | Agent |
| --- | --- | --- |
| 注册 | `bind_tools([...])` | `create_agent(tools=[...])` |
| 执行 | 自己写循环 | 框架自动执行 |
| 回填 | 手动 append `ToolMessage` | 自动 append |

day04 讲的是左列，day06 讲的是右列，重点在「工具本身还能拿到什么」。

### 1.2 创建工具的三种精细度

**基础形态：`@tool` + docstring + 类型注解**

```python
@tool
def search_database(query: str, limit: int = 10) -> str:
    """Search the customer database for records matching the query.

    Args:
        query: Search terms to look for
        limit: Maximum number of results to return
    """
    return f"Found {limit} results for '{query}'"
```

docstring 就是工具的 description，类型注解就是参数的 JSON Schema。**docstring 里把参数含义写清楚，比在代码里写注释重要得多**——这份描述是给模型看的。

**自定义名称与描述**

```python
@tool("calculator", description="Performs arithmetic calculations. Use this for any math problems.")
def calc(expression: str) -> str:
    ...
```

需要「函数名对模型不友好」或想强化使用场景时用。

**高级 schema：`args_schema`**

```python
class WeatherInput(BaseModel):
    location: str = Field(description="City name or coordinates")
    units: Literal["celsius", "fahrenheit"] = Field(default="celsius")
    include_forecast: bool = Field(default=False)

@tool(args_schema=WeatherInput)
def get_weather(location: str, units: str = "celsius", include_forecast: bool = False) -> str:
    ...
```

也支持直接传 JSON Schema 字典。`args_schema` 的价值是**给每个参数写 description、加枚举约束、设默认值**——参数越复杂，模型越需要这些提示。

### 1.3 ToolRuntime：工具的「后台通道」

这是 day06 工具部分最重要的机制。工具函数加一个 `runtime: ToolRuntime` 参数，就能拿到六类运行时信息，**而这个参数对模型完全隐藏**（不会出现在工具 schema 里，模型不知道它的存在）。

| 组成 | 说明 | 典型用途 |
| --- | --- | --- |
| `state` | 短期记忆，当前对话的可变数据（消息、计数器、自定义字段） | 读历史消息、读自定义状态 |
| `context` | 调用时传入的不可变配置（user_id、会话信息） | 按用户身份个性化 |
| `store` | 长期记忆，跨对话持久数据 | 存用户偏好、知识库 |
| `stream_writer` | 工具执行中实时发进度 | 长任务进度反馈 |
| `config` | 执行的 `RunnableConfig` | 访问回调、标签、元数据 |
| `tool_call_id` | 当前工具调用的唯一 ID | 日志关联、手工构造 ToolMessage |

**这个设计的精髓**：模型只看到业务参数（如 `pref_name`），看不到 `runtime`；但工具内部能借 runtime 读到「模型不该也不需要知道」的环境信息。安全边界和功能扩展同时满足。

代码示例的结构值得记住：

```python
@tool
def get_user_preference(pref_name: str, runtime: ToolRuntime) -> str:
    """获取用户传入的参数。"""
    preferences = runtime.state.get("user_preferences", {})
    return preferences.get(pref_name, "Not set")
```

模型负责决定「要查哪个偏好」，runtime 负责提供「当前是谁」。

### 1.4 ToolNode、预构建工具、服务端工具

- **ToolNode**：LangGraph 的预构建节点，在自定义图里执行工具，自动处理并行执行、错误处理和状态注入。用 `create_agent` 时不需要手动碰它；自己搭 LangGraph 图才需要。
- **预构建工具包**：网页搜索、代码解释、数据库访问等常见能力，官方和社区已有现成实现，直接导入即可，不必重写。
- **服务端工具**：由模型厂商在自己的服务器上执行的工具（如 web_search）。用法是 `model.bind_tools([{"type": "web_search"}])`，自己不写任何逻辑，工具执行过程也不可见。

三者对应三种「工具从哪来」：自己写 / 用现成的 / 厂商代劳。

## 2. 短期记忆（Short-term memory）

### 2.1 概念与边界

短期记忆 = **单个线程（thread）内的对话状态**。类比聊天软件：同一个聊天窗口里的历史都在，换个窗口就是新会话。

为什么要专门管它：完整历史塞不进上下文窗口，而且即使塞得进，长上下文也会让模型被陈旧内容干扰、响应变慢、成本变高。所以「记住」和「该忘」是一体的。

### 2.2 基本使用：checkpointer + thread_id

```python
from langgraph.checkpoint.memory import InMemorySaver

agent = create_agent(model, checkpointer=InMemorySaver())
res = agent.invoke(
    {"messages": [{"role": "user", "content": "Hi! My name is Bob."}]},
    {"configurable": {"thread_id": "1"}},
)
```

两个要素缺一不可：

- **`checkpointer`** 负责持久化状态（内存或数据库）
- **`thread_id`** 负责隔离会话

**只配 checkpointer 不传 thread_id，等于没有记忆**——每次调用都会被当成新线程。这是最常见的踩坑点。

生产环境把状态存数据库：

```python
import pymysql
from langgraph.checkpoint.mysql.pymysql import PyMySQLSaver

connection = pymysql.connect(host=..., user=..., password=..., database="langchain02", autocommit=True)
checkpointer = PyMySQLSaver(connection)
checkpointer.setup()          # 自动建表
```

库要自己建，表和数据由 LangChain 写入。也可以走 `PyMySQLSaver.from_conn_string(DB_URI)` 的连接串写法。

### 2.3 扩展状态：记住消息之外的信息

```python
class CustomAgentState(AgentState):
    user_id: str
    preferences: dict

agent = create_agent(model, state_schema=CustomAgentState, checkpointer=InMemorySaver())
agent.invoke({
    "messages": [{"role": "user", "content": "Hello"}],
    "user_id": "user_123",
    "preferences": {"theme": "dark"},
}, {"configurable": {"thread_id": "1"}})
```

自定义字段必须继承 `AgentState`，并在 invoke 时一并传入。day03 讲过另一种「中间件 `state_schema`」的写法，这里用 `create_agent(state_schema=)` 是等价能力，区别只是作用范围。

### 2.4 上下文超限的四种策略

这是短期记忆真正的工程难点。课件列了四条路：

| 策略 | 做法 | 代价 |
| --- | --- | --- |
| 修剪消息 | 调模型前只保留最近 N 条 | 早期信息丢失 |
| 删除消息 | 用 `RemoveMessage` 永久删除 | 同上，且不可逆 |
| 总结消息 | 让模型把旧消息压成摘要 | 多一次模型调用，摘要可能失真 |
| 自定义策略 | 消息过滤等 | 要自己维护逻辑 |

**修剪：`@before_model` + `RemoveMessage`**

```python
@before_model
def trim_messages(state: AgentState, runtime: Runtime):
    messages = state["messages"]
    first_msg = messages[0]
    return {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), first_msg, *messages[-3:]]}
```

`REMOVE_ALL_MESSAGES` 是「清空」的哨兵值，先清空再放回要保留的消息。要先删后加，不能只 add。

**删除：按 id 精确删除**

```python
return {"messages": [RemoveMessage(id=m.id) for m in messages[:2]]}   # 删最早两条
```

`RemoveMessage` 能生效的前提是状态键使用了 `add_messages` reducer——默认的 `AgentState` 已经具备。

**总结：`SummarizationMiddleware`**

```python
mid = SummarizationMiddleware(
    model=model,                 # 用哪个模型做总结
    trigger=("tokens", 4000),    # 超过 4000 token 触发
    keep=("messages", 20),       # 总结后保留最近 20 条
)
```

三条参数各有含义：`trigger` 定触发条件（也可按消息条数），`keep` 定保留量，`model` 是执行总结的模型（省钱可以换小模型）。

课件演示了修剪的实际后果：连续聊了五六轮后问「我多大了」，模型答不出来——因为早期那条「my age is 30」已被裁掉。**这不是 bug，是策略的必然代价**，产品上要接受或用总结策略缓解。

### 2.5 记忆能在哪访问

| 位置 | 访问方式 |
| --- | --- |
| 工具 | `runtime.state` / `runtime.context` |
| 提示词（dynamic_prompt） | `request.runtime.context[...]`、`request.messages` |
| `before_model` | `state["messages"]` |
| `after_model` | `state["messages"]` |

### 2.6 工具内读写状态

**读**：`runtime.state["user_id"]` 或 `runtime.state.get("user_name")`。

**写**：工具返回 `Command(update={...})` 而不是普通字符串。

```python
@tool
def update_user_info(runtime: ToolRuntime[CustomContext, CustomState]) -> Command:
    """Look up and update user info."""
    user_id = runtime.context.user_id
    name = "John Smith" if user_id == "user_123" else "Unknown user"
    return Command(update={
        "user_name": name,
        "messages": [ToolMessage("成功查询用户信息", tool_call_id=runtime.tool_call_id)],
    })
```

两个细节不能漏：

1. **`update` 里必须手动补一条 `ToolMessage`**，且 `tool_call_id=runtime.tool_call_id`。原因是工具已经不走默认的「返回字符串→自动包 ToolMessage」路径，消息链得自己接上，否则对话结构不合法。
2. `Command` 除了 `update` 还支持 `goto`，可以做「工具调用后跳转到某个节点」的流程控制（day07 的多智能体就靠这个）。

课件里还有一个很巧妙的设计：`greet` 工具发现 `user_name` 为空时，不报错，而是返回 `Command` 带一条 ToolMessage 提示模型「请先调 update_user_info」。**用工具消息引导模型走向正确流程**，比抛异常优雅得多。

## 3. 护栏（Guardrails）

### 3.1 为什么必须有

护栏是在 Agent 执行关键点做验证和过滤的机制。课件举的例子很直白：问「如何制作炸药」「如何生成违规图片」「政治敏感话题」，这些请求**不应该进入大模型**，应该在调用前就被拦下。

产品上线必须合规，护栏不是可选项。常见用例：防 PII 泄露、防提示注入、阻止有害内容、执行业务规则、校验输出质量。

### 3.2 两种互补方法

| | 确定性护栏 | 基于模型的护栏 |
| --- | --- | --- |
| 实现 | 正则、关键词、明确规则 | LLM 或分类器做语义判断 |
| 优点 | 快、可预测、便宜 | 能抓住规则遗漏的微妙问题 |
| 缺点 | 会漏细微违规 | 慢、贵 |
| 适合 | 明确的黑名单、格式校验 | 语义级合规判断 |

实践用法是两层叠加：确定性护栏挡明显的，模型护栏兜语义层面的。

### 3.3 内置护栏：PIIMiddleware

```python
agent = create_agent(
    model=model,
    middleware=[
        PIIMiddleware("email", strategy="redact", apply_to_input=True),
        PIIMiddleware("credit_card", strategy="mask", apply_to_input=True),
        PIIMiddleware("api_key", detector=r"sk-[a-zA-Z0-9]{32}", strategy="block", apply_to_input=True),
    ],
)
```

三个参数决定行为：

| 参数 | 取值 | 含义 |
| --- | --- | --- |
| 实体 / `detector` | `"email"`、`"credit_card"`、`"api_key"` 等，或自定义正则 | 检测什么 |
| `strategy` | `redact` / `mask` / `block` | 编辑掉 / 遮盖 / 直接抛错 |
| `apply_to_input` | 布尔 | 是否作用于用户输入 |

三者是递进强度：`redact` 把内容删掉、`mask` 保留形状盖住、`block` 直接拒绝。选择取决于业务：邮箱适合 redact，信用卡适合 mask（用户还要核对后四位），API key 适合 block。

### 3.4 自定义护栏：基于类 + 钩子

**执行前拦截（黑名单式）**

```python
class ContentFilterMiddleware(AgentMiddleware):
    def __init__(self, banned_keywords: list[str]):
        super().__init__()
        self.banned_keywords = [kw.lower() for kw in banned_keywords]

    @hook_config(can_jump_to=["end"])
    def before_agent(self, state: AgentState, runtime: Runtime):
        first_message = state["messages"][0]
        content = first_message.content.lower()
        for keyword in self.banned_keywords:
            if keyword in content:
                return {
                    "messages": [{"role": "assistant", "content": "我不能回答你这个问题，请换个问题."}],
                    "jump_to": "end",
                }
        return None
```

三个关键点：

1. **`before_agent`** 在 Agent 启动前执行，一次调用只跑一次，适合做「进门检查」。
2. **`@hook_config(can_jump_to=["end"])`** 是声明式的「我要提前结束」，不声明就不能 `jump_to`。
3. **返回值**里放一条 assistant 消息 + `jump_to: "end"`，等于「直接给用户答复并终止流程」，模型根本没被调用。

**执行后审查（模型式）**

```python
class SafetyGuardrailMiddleware(AgentMiddleware):
    def __init__(self):
        super().__init__()
        self.safety_model = init_chat_model(model="deepseek-chat", ...)   # 专职审查的小模型

    @hook_config(can_jump_to=["end"])
    def after_agent(self, state: AgentState, runtime: Runtime):
        last_message = state["messages"][-1]
        result = self.safety_model.invoke([{"role": "user", "content": safety_prompt}])
        if "UNSAFE" in result.content:
            return {"messages": [{"role": "assistant", "content": "我不能回答你这个问题."}], "jump_to": "end"}
        return None
```

`after_agent` 在 Agent 完成后运行，能看到最终输出。用一个独立模型做审查（而不是让主模型自审），职责分离，也更可靠。

## 4. MCP（Model Context Protocol）

### 4.1 定位

MCP 是标准化「应用如何向 LLM 提供工具和上下文」的开放协议。LangChain 通过 `langchain-mcp-adapters` 使用 MCP server 上定义的工具。

现实意义：**大部分 MCP server 不需要你写**。第三方开源的、公司其他部门部署好的（如 12306 查票 server），你只要知道它有哪些功能，配好让大模型自己选就行。

```bash
pip install langchain-mcp-adapters
```

### 4.2 三种传输方式

| 传输 | 机制 | 取舍 |
| --- | --- | --- |
| `stdio` | 客户端把 server 作为子进程启动，走标准输入输出 | 本地工具、简单，但要管进程 |
| `streamable_http` | server 独立进程，处理 HTTP 请求 | 支持远程和多客户端，**推荐** |
| `sse` | Streamable HTTP 的变体，面向实时流式 | **已弃用** |

课件的建议很明确：以后尽量用 HTTP，stdio 用得少。

### 4.3 服务端（FastMCP）

```python
from mcp.server.fastmcp import FastMCP
mcp = FastMCP("数学计算")

@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b

if __name__ == "__main__":
    mcp.run(transport="stdio")          # 或 "streamable-http"
```

同一个 server 改一行 `transport` 就能切换传输方式。`streamable-http` 默认监听 8000 端口、路径 `/mcp`。

### 4.4 客户端（LangChain 侧）

```python
from langchain_mcp_adapters.client import MultiServerMCPClient

client = MultiServerMCPClient({
    "math": {
        "transport": "stdio",
        "command": "python",
        "args": [r"D:\...\stdio的fastmcp服务端.py"],     # 必须绝对路径
    },
    "weather": {
        "transport": "streamable_http",
        "url": "http://localhost:8000/mcp",
    },
})

async def main():
    tools = await client.get_tools()        # 关键一行：MCP 工具转成 LangChain 工具
    agent = create_agent(model=model, tools=tools)
    await agent.ainvoke({...})

asyncio.run(main())
```

整条链路的精髓就在 `client.get_tools()`：MCP 协议上的工具被适配成 LangChain 的 Tool 对象，之后和 `@tool` 手写的工具**完全没有区别**，直接丢给 `create_agent` 即可。这正是「协议统一」带来的好处——不需要改 Agent 代码就能接入新工具源。

### 4.5 与其他能力的关系

课件里那句总结值得记：**大模型 + MCP 服务 + 自带函数 = AI 智能体**。拆开看：

- 生成文案 → 大模型
- 打开微信发朋友圈、填邮箱发送 → 工具（可以是本地 tool，也可以是 MCP server）
- 谁来选、谁来判断顺序 → Agent

所以 Function Calling、MCP、工具调用不是三个竞争技术，而是同一件事的三层：底层机制、协议标准、使用形式。

## 5. 人机交互（HITL）

### 5.1 解决的问题

有些工具调用不该让模型自己决定：写文件、执行 SQL、发邮件、转账。HITL 中间件在工具调用前暂停执行，等人工决策。

机制：`HumanInTheLoopMiddleware` 按可配置策略检查每个工具调用；需要干预时发出 `interrupt` 停止执行，状态通过 LangGraph 持久化层保存，之后可以安全恢复。

### 5.2 配置

```python
interrupt_config = {
    "write_file_tool": True,                                        # 允许 approve / edit / reject
    "execute_sql_tool": {"allowed_decisions": ["approve", "reject"]}, # 只允许批准或拒绝（不许改 SQL）
    "read_data_tool": False,                                        # 无需批准
}

middleware = HumanInTheLoopMiddleware(
    interrupt_on=interrupt_config,
    description_prefix="⚠️ [安全审查] 待批准的操作:",
)

agent = create_agent(model=model, tools=[...], middleware=[middleware], checkpointer=MemorySaver())
```

`interrupt_on` 三种取值：

| 值 | 含义 |
| --- | --- |
| `True` | 三种决策都允许（approve / edit / reject） |
| `{"allowed_decisions": [...]}` | 精确指定允许哪几种 |
| `False` | 不需要人工干预 |

**`checkpointer` 是必需的**：中断意味着「暂停后还能恢复」，没有持久化就恢复不了。

### 5.3 三种决策

| 决策 | 行为 | 典型场景 |
| --- | --- | --- |
| `approve` | 按原样执行 | 确认邮件内容后直接发送 |
| `edit` | 修改参数后执行 | 发送前把收件人改掉 |
| `reject` | 拒绝执行，并说明原因 | 拒绝这份草稿并指出怎么改 |

「改 SQL 参数」这种高风险操作，用 `allowed_decisions: ["approve", "reject"]` 把 `edit` 关掉——**不允许人工改语句后执行，只允许原样执行或放弃**。这是权限设计上很实用的一招。

### 5.4 中断与恢复流程

```python
config = {"configurable": {"thread_id": "user_123_session_abc"}}
result = agent.invoke({"messages": [{"role": "user", "content": "执行sql，删除数据库中用户的记录。"}]}, config=config)

if "__interrupt__" in result:
    # 等待人工决策
    if 用户确认:
        res = agent.invoke(Command(resume={"decisions": [{"type": "approve"}]}), config=config)
    else:
        res = agent.invoke(Command(resume={"decisions": [{"type": "reject"}]}), config=config)
```

四个要点：

1. **`__interrupt__` 是结果字典里的键**，出现即代表「暂停了，需要决策」。
2. **恢复必须用同一个 `thread_id`**，否则接不上暂停时的状态。
3. **`Command(resume={"decisions": [...]})`** 是固定的恢复格式，`decisions` 是列表。
4. **多个工具同时被中断时，决策顺序必须与中断请求中出现的顺序一致**——顺序错了会把批准给了错误的操作。

`edit` 形态的决策带修改后的参数（形如 `{"type": "edit", "args": {...}}`），具体字段以实际中间件版本为准。

## 6. 踩坑清单

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| 工具里拿不到 `runtime` | 参数没写 `runtime: ToolRuntime` | 补上类型注解，它会自动注入且对模型隐藏 |
| 短期记忆完全没生效 | 没传 `thread_id` | `invoke(..., {"configurable": {"thread_id": "..."}})` |
| 换台机器历史就没了 | 用 `InMemorySaver` | 换 `PyMySQLSaver` 等数据库实现 |
| `PyMySQLSaver` 报表不存在 | 只管建表不管建库 | 先手动建库，再 `checkpointer.setup()` |
| 修剪后模型「失忆」 | 早期消息被裁掉，属策略代价 | 接受，或改 `SummarizationMiddleware` |
| 删消息后请求报错 | 删掉了 assistant tool_calls 对应的 tool 结果 | 删除时保证消息链合法（tool_calls 后必须有 tool 结果） |
| 总结中间件报错 | 没给它 `model` | `SummarizationMiddleware(model=..., trigger=..., keep=...)` |
| PII 检测漏掉部分 key | `detector` 正则固定 `{32}` 位 | 按实际 key 长度调整正则，或用内置实体 |
| 黑名单护栏只在第一轮生效 | `before_agent` 只看 `messages[0]` | 多轮场景改为检查最后一条 human 消息 |
| `jump_to` 不生效 | 没加 `@hook_config(can_jump_to=["end"])` | 补装饰器 |
| MCP stdio 启动失败 | `args` 用了相对路径 | 写绝对路径，`command` 用可执行名或完整解释器路径 |
| `get_tools()` 没返回 | 忘了 `await` | 它是异步函数，`tools = await client.get_tools()` |
| HITL 无法恢复 | 没配 `checkpointer` | 加 `checkpointer=MemorySaver()` |
| 恢复后状态错乱 | `thread_id` 变了 | 恢复时用同一个 config |
| 决策批错了操作 | 多个中断时顺序不对 | `decisions` 顺序与中断请求顺序严格一致 |
| `runtime.stream_writer` 报错 | 不在 LangGraph 执行上下文中 | 必须在 agent 运行时调用，不能单独测试工具函数 |

## 7. 关键知识清单（速查）

**工具**

- `@tool` + docstring + 类型注解 = 工具说明书；docstring 是给模型看的
- 三种精细度：基础装饰 / 自定义 name+description / `args_schema`（Pydantic 或 JSON Schema）
- `ToolRuntime` 六件套：`state`、`context`、`store`、`stream_writer`、`config`、`tool_call_id`；参数对模型隐藏
- ToolNode（LangGraph 节点）/ 预构建工具包 / 服务端工具（`{"type": "web_search"}`）

**短期记忆**

- 两要素：`checkpointer` + `thread_id`；缺 thread_id 等于没记忆
- 存储：`InMemorySaver`（开发）/ `PyMySQLSaver`（生产，`setup()` 自动建表）
- 扩展状态：继承 `AgentState`，`state_schema=` 声明，invoke 时传字段
- 四种超限策略：修剪 / 删除 / 总结 / 自定义
- 删除用 `RemoveMessage(id=...)`，清空用 `REMOVE_ALL_MESSAGES`
- 总结用 `SummarizationMiddleware(model, trigger, keep)`
- 工具写状态：返回 `Command(update={..., "messages": [ToolMessage(..., tool_call_id=runtime.tool_call_id)]})`

**护栏**

- 两类：确定性（快、便宜、会漏）/ 基于模型（慢、贵、能抓语义）
- 内置 `PIIMiddleware(entity, strategy=redact|mask|block, detector, apply_to_input)`
- 自定义：`AgentMiddleware` + `before_agent` / `after_agent` + `@hook_config(can_jump_to=["end"])`
- 拦截返回：`{"messages": [assistant 消息], "jump_to": "end"}`

**MCP**

- 装 `langchain-mcp-adapters`；三种传输：stdio / streamable_http / sse（弃用）
- 服务端：FastMCP + `mcp.run(transport=...)`
- 客户端：`MultiServerMCPClient({...})` → `await client.get_tools()` → `create_agent(tools=tools)`
- 核心价值：MCP 工具适配后与本地 `@tool` 无差别

**HITL**

- `HumanInTheLoopMiddleware(interrupt_on={工具名: True | {allowed_decisions} | False}, description_prefix=...)`
- 必须配 `checkpointer`
- 三种决策：`approve` / `edit` / `reject`
- 中断标志：`result["__interrupt__"]`
- 恢复：`agent.invoke(Command(resume={"decisions": [{"type": "approve"}]}), config=同 thread_id)`
- 多中断时决策顺序必须与中断顺序一致
