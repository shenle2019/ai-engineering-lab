# LangChain 流式传输与结构化输出

> 来源：python 山顶会三期 day05（LangChain 结构化输出和流式输出），课件 `day14-课堂笔记.md` + 代码包第 6–7 章
> 定位：理解向笔记，记录机制、要点与踩坑，不复刻课件代码

## 0. 这份内容在讲什么

day05 把两个「体验层」能力讲透，它们共同决定了一个 Agent 产品好不好用：

```
流式传输（Streaming）                    结构化输出（Structured output）
├─ 解决：模型慢，用户干等                 ├─ 解决：模型输出是自然语言，程序没法直接用
├─ updates：按节点看进度                  ├─ response_format 四种取值
├─ messages：按 token 看生成              ├─ ProviderStrategy：供应商原生
├─ custom：工具内部自定义进度              ├─ ToolStrategy：借工具调用兜底
└─ 可组合 / 可禁用                        └─ 校验失败自动重试 + 错误处理策略
```

一句话概括两者：**流式解决「等得难受」，结构化解决「拿到没法用」。**

## 1. 流式传输（Streaming）

### 1.1 为什么需要流式

LLM 的延迟是物理性的：一次完整响应可能要几秒到几十秒。流式的价值是把「一次性等完整结果」变成「边生成边展示」——即使总时长不变，用户感知的响应速度完全不同。医疗问诊、客服这类场景尤其明显：血压数据一条条出，比憋十秒一次性弹出体验好得多。

### 1.2 LangChain 能流什么

| 流什么 | 用什么模式 | 粒度 |
| --- | --- | --- |
| Agent 进度 | `stream_mode="updates"` | 每个节点执行完发一次事件 |
| LLM 生成的 token | `stream_mode="messages"` | 每个 token / 每个内容块 |
| 自定义信号 | `stream_mode="custom"` | 工具内部想发什么就发什么 |
| 完整状态快照 | `stream_mode="values"` | 每个步骤后的整个 state |

（`values` 在 day03 已用过，取 `chunk["messages"][-1]`。）

### 1.3 updates：按节点看进度

```python
for chunk in agent.stream(
    {"messages": [{"role": "user", "content": "上海的天气怎么样?"}]},
    stream_mode="updates",
):
    for step, data in chunk.items():
        print(f"step: {step}")
        print(data["messages"][-1].content_blocks)
```

返回结构是 `{节点名: 该节点产出的状态片段}`。一次「问天气」的典型事件序列：

```
step: model   content: [{'type': 'tool_call', 'name': 'get_weather', 'args': {'city': '上海'}, 'id': 'call_xxx'}]
step: tools   content: [{'type': 'text', 'text': "It's always sunny in 上海!"}]
step: model   content: [{'type': 'text', 'text': '上海的天气总是晴朗的！'}]
```

这三行就是 Agent 循环的完整证据链：**模型决定调工具 → 工具执行 → 模型总结**。想在前端画「正在调用工具…」这类状态，用 `updates` 最合适。

### 1.4 messages：按 token 看生成

```python
for token, metadata in agent.stream(
    {"messages": [{"role": "user", "content": "上海的天气怎么样?"}]},
    stream_mode="messages",
):
    print(metadata["langgraph_node"])
    print(token.content_blocks)
```

注意返回的是**二元组** `(token, metadata)`，`metadata["langgraph_node"]` 告诉你这个 token 来自哪个节点（`model` 还是 `tools`）。

课件给出的实际事件流很能说明问题：

```
node: model  content: [{'type': 'tool_call_chunk', 'id': 'call_xxx', 'name': 'get_weather', 'args': '', 'index': 0}]
node: model  content: [{'type': 'tool_call_chunk', 'id': '', 'name': '', 'args': '{"city": "', 'index': 0}]
node: model  content: [{'type': 'tool_call_chunk', 'id': '', 'name': None, 'args': '上海"}', 'index': 0}]
node: model  content: []        ← 空块，要跳过
node: tools  content: [{'type': 'text', 'text': "It's always sunny in 上海!"}]
node: model  content: [{'type': 'text', 'text': '上海'}]
node: model  content: [{'type': 'text', 'text': '的天气总是'}]
...
```

三个必须处理的现实：

1. **工具调用的参数是分片到达的**，要按 `index` 拼接（day04 的 `chunk + chunk` 就是干这个）。
2. **会有大量空 `content_blocks`**（`[]`），直接渲染会出现空帧，必须过滤。
3. **工具节点的输出也会以 text 块出现**，前端要区分「模型回答」和「工具输出」，否则用户会看到工具返回值闪一下。

### 1.5 custom：工具内部发进度

工具自己发进度信号，用 LangGraph 的 `get_stream_writer`：

```python
from langgraph.config import get_stream_writer

@tool
def get_weather(city: str) -> str:
    """获取给定城市的天气。"""
    writer = get_stream_writer()
    writer(f"正在查询城市: {city}")
    writer(f"已获取城市数据: {city}")
    return f"{city} 晴"
```

消费端：

```python
for chunk in agent.stream({...}, stream_mode="custom"):
    print(chunk)          # 直接就是 writer 发出的内容
```

工具内部还有一条等价路径：`runtime.stream_writer`（ToolRuntime 提供，day06 会讲）。两者作用相同——**让长耗时工具能持续汇报进度**，而不是让用户盯着转圈。

课件举的场景很典型：拉取 100 条记录，每 10 条报一次「Fetched 10/100」，比最后一次性返回友好得多。

### 1.6 多模式组合

```python
for stream_mode, chunk in agent.stream({...}, stream_mode=["updates", "custom"]):
    print(stream_mode, chunk)
```

传列表后，循环变量从「单值」变成「`(模式名, 数据)` 二元组」。这是最容易踩的语法坑：单模式和多模式的解包方式不同。

组合的实用价值：一个前端界面同时要「节点状态」（updates）和「工具进度」（custom），一次请求就能拿到两种流。

### 1.7 禁用流式

```python
model = ChatOpenAI(model=..., streaming=False)
```

这是**模型级**开关，不是 agent 级。典型场景是多模型 Agent：千问正常流式，DeepSeek 关掉流式（比如为了拿完整结构化结果或省钱），到了 DeepSeek 回答的阶段就不流式输出，即使外层调的是 `agent.stream()`。

## 2. 结构化输出（Structured output）

### 2.1 概念回顾

day04 讲的是「裸 Model」的结构化输出（`with_structured_output`）。day05 讲的是 **Agent 层**的结构化输出（`create_agent(response_format=...)`）。

区别在于：Agent 里结构化输出不是终点的唯一形态——模型可能先调工具、再产出结构化结果，框架要保证这个过程能跑通并自动校验。

```python
result = agent.invoke({"messages": [...]})
result["structured_response"]      # 结构化结果永远在这个键里
```

**这是最重要的定位信息**：结构化结果不占 `messages[-1]`，而在独立的 `structured_response` 键。取错地方就会拿到自然语言文本。

### 2.2 response_format 四种取值

```python
def create_agent(
    ...,
    response_format: Union[
        ToolStrategy[StructuredResponseT],
        ProviderStrategy[StructuredResponseT],
        type[StructuredResponseT],
        None,
    ],
)
```

| 取值 | 含义 |
| --- | --- |
| `ToolStrategy[Schema]` | 借工具调用来实现结构化输出，通用于支持工具调用的模型 |
| `ProviderStrategy[Schema]` | 用供应商原生结构化输出能力 |
| `Schema`（直接传类型） | 让 LangChain 按模型能力自动选 |
| `None` | 不做结构化输出（默认） |

自动选择规则：模型支持原生 → `ProviderStrategy`；否则 → `ToolStrategy`。

### 2.3 ProviderStrategy：供应商原生

**原理**：直接把 schema 交给厂商 API，由厂商保证输出符合 schema。这是最可靠、最少 token 浪费的方式。

**限制**：只对原生支持的供应商有效。课件实测：

- `qwen-plus` 正常
- `deepseek-chat` 报错 `this response_format type is unavailable now`

**支持的 schema 类型**（四种都能用）：

| 类型 | 返回形态 |
| --- | --- |
| Pydantic `BaseModel` | 对象，带字段校验 |
| `@dataclass` | 数据类实例 |
| `TypedDict` | 字典 |
| 原始 JSON Schema | 字典 |

四种写法的差异只在「怎么描述 schema」，其余调用方式完全一样。选型建议：**要校验用 Pydantic，要轻量用 TypedDict，要和外部系统对接用 JSON Schema。**

### 2.4 ToolStrategy：借工具调用兜底

**原理**：LangChain 内部临时注册一个「结构化输出工具」，其参数 schema 就是你的目标 schema。模型以为自己在调工具，实际是借这条通道把结构化数据交出来，LangChain 再把工具参数解析成目标对象。

**代价**：多一轮工具调用，比原生方式更耗资源。课件的注释写得很直白：「会比大模型直接支持，耗费资源，因为内部调用了工具」。

**收益**：几乎所有支持工具调用的模型都能用，包括不支持原生结构化输出的 DeepSeek。

三个参数：

| 参数 | 作用 |
| --- | --- |
| `schema` | 目标结构，支持 Pydantic / Dataclass / TypedDict / JSON Schema / **Union 联合类型** |
| `tool_message_content` | 自定义「结构化输出工具」返回给模型的消息文本 |
| `handle_errors` | 校验失败时的重试策略，默认 `True` |

**`tool_message_content` 的实际影响**：不加时，最终 AI 消息里会出现 `Returning structured response: task=... assignee=...` 这类框架生成的文本；加了之后，AI 消息变成你指定的那句话（如「行动事项已捕获并添加到会议记录中！」）。**注意：`structured_response` 里的对象不受影响**，变的只是给人看的文本。

联合类型是 ToolStrategy 独有的能力：

```python
response_format=ToolStrategy(Union[ContactInfo, EventDetails])
```

模型会根据上下文选最合适的那个 schema。

### 2.5 错误处理：LangChain 替你重试

这是 day05 最有工程价值的部分。结构化输出会出两类错，框架都能自动纠正。

**错误一：返回了多个结构化结果**

用 `Union[ContactInfo, EventDetails]` 时，模型可能贪心，一次调两个工具：

```
AI: Tool Calls: ContactInfo(call_1), EventDetails(call_2)
Tool(ContactInfo): Error: Model incorrectly returned multiple structured responses ... Please fix your mistakes.
Tool(EventDetails): Error: 同上
AI: Tool Calls: ContactInfo(call_3)      ← 模型改正，只调一个
Tool(ContactInfo): Returning structured response: {'name': 'John Doe', ...}
```

关键机制：**错误是以 `ToolMessage` 的形式反馈给模型的**，模型看到「你只能给一个」的提示后自己重试。这是「用对话纠错代替抛异常」的设计。

**错误二：schema 校验不通过**

```
AI: Tool Calls: ProductRating(rating=10)      ← 用户说 10/10，模型照抄
Tool: Error: 1 validation error for ProductRating.rating
      Input should be less than or equal to 5 [input_value=10]
AI: Tool Calls: ProductRating(rating=5)       ← 模型改正
Tool: Returning structured response: {'rating': 5, ...}
```

Pydantic 的 `ge=1, le=5` 约束在这里真正发挥了作用：**校验发生在框架侧，纠错提示自动回传给模型**。这也说明为什么建议用 Pydantic 而不是 TypedDict——TypedDict 没有运行时校验，这类错误根本拦不住。

**`handle_errors` 六种取值**

| 取值 | 行为 |
| --- | --- |
| `True`（默认） | 捕获所有错误，用默认模板提示重试 |
| 字符串 | 捕获所有错误，用这句固定话术提示重试 |
| `ValueError` | 只在该异常类型时重试，其它照常抛出 |
| `(ValueError, TypeError)` | 只在这些异常类型时重试 |
| 可调用对象 | 自定义函数，按异常类型返回不同提示 |
| `False` | 不重试，直接抛异常 |

自定义处理函数的价值在于「按错误类型给不同话术」：

```python
def custom_error_handler(error: Exception) -> str:
    if isinstance(error, StructuredOutputValidationError):
        return "格式存在问题。请重试。"
    elif isinstance(error, MultipleStructuredOutputsError):
        return "返回了多个结构化输出。请选择最相关的一个。"
    ...
```

## 3. 踩坑清单

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| 拿不到结构化结果 | 去 `messages[-1]` 找了 | 结构化结果在 `result["structured_response"]` |
| 换个模型就报 `unavailable` | `ProviderStrategy` 依赖供应商原生支持 | 改用 `ToolStrategy`，或直传 schema 让它自动降级 |
| 结构化输出比预期慢/贵 | `ToolStrategy` 多一轮工具调用 | 能用原生就用 `ProviderStrategy` |
| 联合类型报「multiple structured responses」 | 模型一次调了多个 schema | 保持默认 `handle_errors=True`，让框架反馈重试 |
| 校验错误直接抛异常 | `handle_errors=False` | 改回 `True` 或指定异常类型 |
| 加了 `tool_message_content` 后对象变了？ | 实际只改了展示文本 | `structured_response` 不变，别被 AI 消息误导 |
| 流式里出现大量空块 | 模型在 tool_call 前后会发空 `content_blocks` | 渲染前过滤 `if not blocks: continue` |
| 工具参数拼不出来 | `tool_call_chunk` 分片到达 | 按 `index` 累积 `gathered + chunk` |
| 多模式循环解包报错 | 多模式返回 `(mode, chunk)` 二元组 | 单模式 `for chunk`、多模式 `for mode, chunk` |
| 设了 `streaming=False` 好像没用 | 它是模型级开关，不是 agent 级 | 确认配置的是当前实际使用的那个模型对象 |
| JSON Schema 校验必失败 | `required` 里的字段名与 `properties` 不一致 | 手工核对两份字段名（课件此示例就写错了） |

## 4. 关键知识清单（速查）

**流式**

- 四种模式：`updates`（节点进度）/ `messages`（token）/ `custom`（工具自定义）/ `values`（整状态）
- `updates` 返回 `{节点名: 状态片段}`，取 `data["messages"][-1]`
- `messages` 返回 `(token, metadata)`，`metadata["langgraph_node"]` 区分 model / tools
- `custom` 用 `get_stream_writer()`（工具内）或 `runtime.stream_writer`
- 多模式传列表，循环变 `for mode, chunk`
- 禁用流式：模型构造时 `streaming=False`，只影响该模型

**结构化输出**

- Agent 层用 `create_agent(response_format=...)`，结果在 `result["structured_response"]`
- `ProviderStrategy`：原生支持（OpenAI、qwen-plus），最可靠；DeepSeek 不支持
- `ToolStrategy`：借工具调用实现，通用兜底；多一轮调用，更耗资源
- 直传 schema 类型：按模型能力自动选策略
- schema 四形态：Pydantic / Dataclass / TypedDict / JSON Schema；ToolStrategy 额外支持 Union
- `tool_message_content` 只改展示文本，不改结构化对象
- 两类自动纠错：多结果错误、schema 校验错误，都通过 `ToolMessage` 反馈重试
- `handle_errors` 六档：`True` / 字符串 / 异常类型 / 异常元组 / 可调用 / `False`
