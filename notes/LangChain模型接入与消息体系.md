# LangChain 模型接入与消息体系

> 来源：python 山顶会三期 day04（LangChain 核心之 Models 模型和 Messages 消息），课件 `day13-课堂笔记.md` + 代码包第 4–5 章
> 定位：理解向笔记，记录机制、要点与踩坑，不复刻课件代码；凭据一律只写变量名，不记录真实 key

## 0. 这份内容在讲什么

day03 学的是「用 Agent 干活」，day04 把 Agent 的两块地基单独拆开讲透：

```
Models（推理引擎）                      Messages（上下文单位）
├─ 怎么接：四种对接方式                 ├─ 四类消息：System / Human / AI / Tool
├─ 怎么调：invoke / stream / batch      ├─ 三种写法：对象 / 字符串 / 字典
├─ 工具调用：bind_tools + 手动循环       ├─ AI 消息：tool_calls、usage_metadata、chunk 相加
├─ 结构化输出：with_structured_output    ├─ Tool 消息：tool_call_id 必须匹配、artifact
└─ 高级主题：多模态、推理、限流、token…  └─ 消息内容：字符串 / 原生块 / 标准内容块
```

结论先给：**Agent 是 Models + Messages 的组合产物**。看懂这两章，day03 里那些「为什么工具调用能自动回填」「为什么流式能分块」就都通了。

## 1. Models 模型

### 1.1 两种使用位置

| 用法 | 说明 | 场景 |
| --- | --- | --- |
| 与 Agent 一起 | `create_agent(model=...)`，模型在代理循环里被反复调用 | 需要多步推理 + 工具 |
| 独立使用 | `model.invoke(...)`，在代理循环之外直接调 | 文本生成、分类、抽取这类单轮任务 |

day04 全部按「独立使用」讲，这样每个机制都能看清，不被 Agent 的黑盒遮住。

### 1.2 对接厂商的四条路

国内绝大多数厂商都兼容 OpenAI 接口，所以路径比想象中少。

**路径一：`ChatOpenAI`（兼容层，最通用）**

```python
from langchain_openai import ChatOpenAI
model = ChatOpenAI(model="deepseek-chat", api_key=..., base_url="https://api.deepseek.com")
```

只要是 OpenAI 兼容协议，一套代码通吃 DeepSeek、千问、Moonshot 等，只换 `model` 和 `base_url`。

**路径二：`init_chat_model`（按模型名自适应）**

```python
from langchain.chat_models import init_chat_model
model = init_chat_model(model="deepseek-chat", api_key=..., base_url=...)
```

它会根据模型名推断该用哪个集成包。注意两点：

- 内部会优先走官方包（如 `langchain-deepseek`），所以 `base_url` 常常可以省略。
- 对 `langchain_community` 里的社区集成（如 `ChatTongyi`）**不一定能自动推断**，别指望它万能。

**路径三：官方独立包 `ChatDeepSeek`**

```python
from langchain_deepseek import ChatDeepSeek
model = ChatDeepSeek(model="deepseek-chat", api_key=...)   # base_url 内置
```

**路径四：社区包 `ChatTongyi`（通义千问）**

```python
from langchain_community.chat_models import ChatTongyi
model = ChatTongyi(model="qwen-vl-max", api_key=..., base_url=".../compatible-mode/v1")
```

LangChain 官方没有 `langchain-tongyi`，千问的适配是社区提交的，功能完整度不如官方包，但**多模态只有这条路能走**（见 1.7）。

### 1.3 官方包 vs OpenAI 兼容层：到底差在哪

这是面试高频点，答案是：**只有思考模型才有区别**。

| 模型类型 | `ChatDeepSeek`（官方包） | `ChatOpenAI`（兼容层） |
| --- | --- | --- |
| 普通对话模型（`deepseek-chat`） | 无差别 | 无差别 |
| 思考模型（`deepseek-reasoner`） | 返回思考过程 `reasoning_content` | **拿不到思考过程**，该字段为空 |

原因是思考过程不在 OpenAI 的兼容协议里，只有官方适配层才会把它解析成 LangChain 的 `reasoning` 内容块。所以：**要用推理模型，就必须走官方包。**

### 1.4 参数

| 参数 | 说明 |
| --- | --- |
| `model` | 模型名或标识符，必填 |
| `api_key` | 身份验证，建议走 `.env` + `os.getenv` |
| `temperature` | 随机性，高=更有创造性，低=更确定 |
| `timeout` | 单次请求超时（秒） |
| `max_tokens` | 限制响应的 token 总数 |
| `max_retries` | 网络超时/限流时的最大重试次数 |

### 1.5 三个方法

| 方法 | 行为 |
| --- | --- |
| `invoke` | 输入消息，等完整响应生成后一次性返回 |
| `stream` | 边生成边返回 `AIMessageChunk` |
| `batch` | 一次提交多个请求，内部并行，返回结果列表 |

`stream` 的消费方式有一个统一套路——遍历 `chunk.content_blocks`，按块类型分流：

```python
for chunk in model.stream("天空为什么是蓝色？"):
    for block in chunk.content_blocks:
        if block["type"] == "reasoning":
            print("推理：", block.get("reasoning"))
        elif block["type"] == "tool_call_chunk":
            print("工具块：", block)
        elif block["type"] == "text":
            print(block["text"], end="")
```

这个模式在 day05 的 agent 流式里会再出现一次，值得记住。

### 1.6 工具调用（裸 Model 版）

流程和 day01 手写的 Function Calling 完全一致，只是 LangChain 把「写说明书」这步自动化了。

**第一步：绑定工具**

```python
model_with_tools = model.bind_tools([get_weather])
response = model_with_tools.invoke("北京天气怎么样？")
response.tool_calls   # [{'name': 'get_weather', 'args': {'location': '北京'}, 'id': 'call_xxx', 'type': 'tool_call'}]
```

`@tool` 装饰器会自动读取函数 docstring 和类型注解，生成 JSON Schema，不再需要手写。

**第二步：手动执行循环**

```python
messages = [{"role": "user", "content": "北京天气怎么样？"}]
ai_msg = model_with_tools.invoke(messages)
messages.append(ai_msg)                       # 关键：AI 消息必须入栈

for tool_call in ai_msg.tool_calls:
    tool_result = get_weather.invoke(tool_call)   # 传整个 tool_call，自动取 args 和 id
    messages.append(tool_result)                  # 得到 ToolMessage

final = model_with_tools.invoke(messages)     # 再请求一次，拿最终回答
```

`get_weather.invoke(tool_call)` 这个写法值得记：直接把 `tool_call` 字典喂给工具，它会自动拆出 `args` 并把 `id` 写进返回的 `ToolMessage.tool_call_id`，省掉手工对齐的麻烦。

**强制工具调用**

```python
model.bind_tools([tool_1, tool_2], tool_choice="any")     # 必须调其中至少一个，但不指定哪个
model.bind_tools([tool_1, tool_2], tool_choice="tool_1")  # 强制调 tool_1
```

**并行工具调用**

问「北京和上海的天气」时，一次响应里可能返回两个 `tool_calls`。遍历执行即可；要提速就用 `async` 并发执行。

**流式下的工具调用**

工具的参数字符串是分批到达的，必须拼接：

```python
gathered = None
for chunk in model_with_tools.stream("上海天气怎么样？"):
    gathered = chunk if gathered is None else gathered + chunk
    print(gathered.tool_calls)     # 拼到最后一个块时才是完整调用
```

这就是「`AIMessageChunk` 可以相加」的实际用途。课件明确说这种写法麻烦、用得少，但原理必须懂——day05 的 `messages` 流式模式就是这个机制。

### 1.7 结构化输出（裸 Model 版）

目标是让模型直接返回符合 schema 的对象/字典，不用自己解析自然语言。

**方式一：Pydantic（带运行时校验）**

```python
class Movie(BaseModel):
    title: str = Field(..., description="电影标题")
    year: int = Field(..., description="电影上映年份")
    rating: float = Field(..., description="电影评分，满分 10 分")

model_with_structure = model.with_structured_output(Movie)
response = model_with_structure.invoke("提供《盗梦空间》的详细信息")
# response 是 Movie 对象，不是字典
```

**方式二：TypedDict + Annotated（轻量，无运行时校验）**

```python
class MovieDict(TypedDict):
    title: Annotated[str, ..., "电影标题"]
    year: Annotated[int, ..., "电影上映年份"]
```

返回普通字典。适合「只要能取字段，不需要校验」的场景。

**方式三：原始 JSON Schema（最大控制力）**

```python
model.with_structured_output(json_schema, method="json_schema")
```

注意 `method="json_schema"` 这个参数，不写可能走别的实现路径。

**方式四：对象与原始消息并存**

```python
model.with_structured_output(Movie, include_raw=True)   # 同时给解析结果与原始 AIMessage
```

需要在拿结构化数据的同时看 `usage_metadata`、`response_metadata` 时用。

**一个必须知道的差异**：课件里写得很直白——用 `ChatOpenAI` 兼容模式做结构化输出会报错，换成 `init_chat_model`（内部走官方包）就正常。这类「兼容层看起来能跑，某些能力却静默失效」的坑，是选对接方式时最该警惕的。

### 1.8 高级主题十一项

| # | 主题 | 关键点 |
| --- | --- | --- |
| 1 | 多模态 | 需要官方 SDK；千问必须 `ChatTongyi` + `dashscope`，OpenAI 兼容通道不支持；千问文生图模型也不支持 |
| 2 | 模型配置文件 | `model.profile` 给出模型能力档案：`max_input_tokens`、`image_inputs`、`reasoning_output`、`tool_calling` |
| 3 | 推理 | 思考模型输出 `reasoning` 内容块，`invoke` 和 `stream` 都能取 |
| 4 | 本地模型 | `ChatOllama(model="qwen3-vl:2b", base_url="http://localhost:11434")` |
| 5 | 服务端工具 | `bind_tools([{"type": "web_search"}])`，工具由厂商在服务端执行，自己不写逻辑 |
| 6 | 速率限制 | `InMemoryRateLimiter(requests_per_second, check_every_n_seconds, max_bucket_size)` 传给模型的 `rate_limiter` |
| 7 | 代理 | `ChatOpenAI(..., openai_proxy="http://proxy:8080")` |
| 8 | 对数概率 | `logprobs=True, top_logprobs=5`，配 `temperature=0` 使用 |
| 9 | token 统计 | 回调式 `UsageMetadataCallbackHandler` / 上下文管理器 `get_usage_metadata_callback()` |
| 10 | 调用配置 | `config={"run_name":..., "tags":[...], "metadata":{...}, "callbacks":[...]}` |
| 11 | 可配置模型 | 运行时换模型/参数，见下 |

**推理（reasoning）的取法**

```python
for chunk in model.stream("为什么鹦鹉有五颜六色的羽毛？"):
    steps = [r for r in chunk.content_blocks if r["type"] == "reasoning"]
    print(steps if steps else chunk.text)
```

**速率限制的语义**：`requests_per_second=0.1` 等于 10 秒一个请求；`check_every_n_seconds=0.1` 是每 100ms 检查一次令牌桶；`max_bucket_size=10` 控制突发上限。写限流不看这三个参数含义，很容易配出「要么限不住、要么卡死」。

**logprobs 的语义**：模型对每个 token 都给一个概率 \(p \in (0,1]\)，为防止浮点下溢，内部用 \(\log p\) 表示。所以 **logprob 恒为 ≤ 0 的负数**：越接近 0（如 -0.1）越确定，越小（如 -10）越不确定。这是「量化模型置信度」的手段。

**token 统计两法**：回调式适合把 handler 挂在单次调用上；上下文管理器适合统计一段代码块内所有调用的总量，还能按模型分组。

**可配置模型（重点）**

```python
model = init_chat_model(
    model="deepseek-reasoner",
    configurable_fields=("model", "model_provider", "temperature", "max_tokens"),
    config_prefix="first",       # 多模型共存时区分前缀
)
model.invoke("你叫什么名字", config={"configurable": {"first_model": "deepseek-chat", "first_temperature": 0.5}})
```

`config_prefix` 会改变 config 里的 key 名（变成 `first_model`、`first_temperature`），不写前缀时直接用 `model`、`temperature`。这套机制的价值是：**一套链式代码，运行时按场景切模型**（省钱用 chat、难题用 reasoner）。

## 2. Messages 消息

### 2.1 消息是什么

消息是 LangChain 中模型上下文的基本单位，三个组成部分：

- **角色（role）**：区分消息类型（system / user / assistant / tool）
- **内容（content）**：文本、图像、音频、文档等实际负载
- **元数据（metadata）**：`id`、`name`、`response_metadata`、`usage_metadata` 等

关键价值：LangChain 定义了一套**跨厂商统一的消息类型**，同一份消息对象喂给 DeepSeek 和千问行为一致，不需要为每个厂商改代码。

### 2.2 三种写法

```python
# 写法一：消息对象
messages = [SystemMessage("你是话剧演员"), HumanMessage("介绍一下自己"), AIMessage("...")]

# 写法二：字符串（单个 HumanMessage 的语法糖）
model.invoke("介绍一下自己")

# 写法三：字典（最省事，工程里最常用）
messages = [
    {"role": "system", "content": "你是话剧演员"},
    {"role": "user", "content": "介绍一下自己"},
    {"role": "assistant", "content": "..."},
]
```

选择依据：单轮任务用字符串；需要系统指令、多轮历史、多模态时用消息列表（对象或字典都行，对象可读性更好、字典写起来更快）。

### 2.3 四种消息类型

**SystemMessage：人物设定**

设置语气、角色、响应准则。它只在对话开头生效，是所有厂商通用的「人格注入点」。

**HumanMessage：用户输入**

可携带文本、图像、音频、文件。支持元数据：

```python
HumanMessage(content="你好", name="lqz", id="lqz_616564099")
```

`name` 用于区分多用户，`id` 用于追踪。

**AIMessage：模型输出**

五个常用属性：

| 属性 | 用途 |
| --- | --- |
| `text` | 纯文本内容（最常用） |
| `content` | 原始内容，可能是字符串或块列表 |
| `content_blocks` | 标准化后的类型安全内容块列表 |
| `tool_calls` | 模型发起的工具调用，没调则空 |
| `usage_metadata` | token 计数 |
| `response_metadata` | 厂商原始响应元数据（含 logprobs 等） |

`AIMessage` 也可以手动创建后插入历史，模拟「模型说过这句话」，用于构造多轮上下文或回放。

**流式下是 `AIMessageChunk`**，可以相加拼成完整消息：

```python
full = None
for chunk in model.stream("你好"):
    full = chunk if full is None else full + chunk
```

**ToolMessage：工具结果回填**

```python
ToolMessage(content="上海天气晴朗", tool_call_id="call_123", name="get_weather")
```

两条硬规则：

1. **`tool_call_id` 必须与 `AIMessage.tool_calls` 里的 `id` 精确匹配**，否则模型侧无法把结果和调用对上。
2. **`artifact` 字段不会发给模型**，只供代码读取。适合放原始结果、文档 id、页码等「模型不需要看但下游要用的元数据」。

`artifact` 的设计意图很实用：`content` 放模型要读的文本，`artifact` 放下游渲染要用的结构化信息，两不干扰，还不会撑大上下文。

### 2.4 消息内容与标准内容块

`content` 支持三种形态：

| 形态 | 示例 |
| --- | --- |
| 字符串 | `HumanMessage("你好")` |
| 厂商原生块 | `{"type": "text", ...}, {"type": "image_url", "image_url": {"url": ...}}` |
| LangChain 标准块 | `{"type": "text", ...}, {"type": "image", "url": ...}` |

两种块的核心区别：原生块用**厂商字段名**（如 `image_url`），标准块用**统一字段名**（如 `image`、`url`/`base64`/`mime_type`）。标准块的类型安全接口就是 `content_blocks`，也可以用它来初始化消息：

```python
HumanMessage(content_blocks=[
    {"type": "text", "text": "描述这张图"},
    {"type": "image", "url": "https://example.com/a.jpg"},
])
```

`content_blocks` 的解析是**延迟**的：Anthropic 返回 `thinking` 块、OpenAI 返回 `reasoning` 块，通过 `content_blocks` 都会归一成 `ReasoningContentBlock`。这就是「一套代码跨厂商」的实现方式。

**标准内容块清单**

| 分类 | 块类型 | 用途 |
| --- | --- | --- |
| 核心 | `text` | 标准文本输出（`text`、`annotations`、`extras`） |
| 核心 | `reasoning` | 推理步骤（`reasoning`、`extras`） |
| 多模态 | `image` / `audio` / `video` / `file` | 图像 / 音频 / 视频 / 通用文件（PDF 等），支持 `url`、`base64`+`mime_type`、`file_id` 三种来源 |
| 多模态 | `text-plain` | 纯文档文本（.txt、.md） |
| 工具调用 | `tool_call` | 完整工具调用（name / args / id） |
| 工具调用 | `tool_call_chunk` | 流式片段（args 可能是残缺 JSON，带 index） |
| 工具调用 | `invalid_tool_call` | 格式错误的调用，捕获 JSON 解析失败 |
| 服务端工具 | `server_tool_call` / `server_tool_call_chunk` / `server_tool_result` | 厂商在服务端执行的工具（如 web_search） |
| 厂商扩展 | `non_standard` | 逃生舱，放厂商独有结构 |

多模态输入的三种来源形式值得记住（图像/音频/视频/文件都一样）：

```
{"type": "image", "url": "https://..."}                                  # 远程 URL
{"type": "image", "base64": "...", "mime_type": "image/jpeg"}            # 内联 base64
{"type": "image", "file_id": "file-abc123"}                              # 厂商文件 ID（需先上传）
```

## 3. 踩坑清单

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| 思考模型拿不到思考过程 | 走的是 OpenAI 兼容层，`reasoning_content` 不在兼容协议里 | 用官方包（`ChatDeepSeek`）或 `init_chat_model` 走官方适配 |
| `ChatOpenAI` + `with_structured_output` 报错 | 兼容层对结构化输出支持不全 | 换 `init_chat_model` / 官方包 |
| 千问多模态调不通 | 兼容通道不支持多模态 | 用 `ChatTongyi` + 安装 `dashscope` |
| 千问文生图不可用 | LangChain 对千问生图模型支持不好 | 生图换其他厂商 |
| 结构化输出返回空/报错 | JSON Schema 方式漏了 `method="json_schema"` | 补上该参数 |
| 改 `config` 里的 key 报 KeyError | 设了 `config_prefix="first"`，key 变成 `first_model` | 前缀要一起写进 config |
| 工具结果被模型忽略 | `ToolMessage.tool_call_id` 与 `tool_calls[].id` 不匹配 | 用 `tool.invoke(tool_call)` 让框架自动对齐 |
| 流式拿到的工具调用参数残缺 | 每个 chunk 只带一部分 args | `gathered = gathered + chunk` 累积后再读 `tool_calls` |
| 把 `content` 当字符串拼接报错 | 多模态消息的 `content` 是 list | 统一走 `content_blocks` 或 `text` 属性 |
| logprobs 看起来是「负数概率」 | 它是 \(\log p\)，不是 \(p\) | 越接近 0 越确定，越小越不确定 |

课件本身有两处笔误，读的时候要能识别：

- `ReasoningContentBlock` 的 `type` 被写成「始终为 text」，实际应为 `reasoning`。
- 结构化输出示例里 `required` 字段名与 `properties` 不一致（写了 `phone`，属性里是 `QQ`），这样校验必然失败。

## 4. 关键知识清单（速查）

**Models**

- 四种对接：`ChatOpenAI`（通用）/ `init_chat_model`（自适应）/ 官方包 / 社区包（千问）
- 官方包与兼容层的唯一实质差别：思考模型能否拿到 `reasoning_content`
- 三方法：`invoke`（等完整）/ `stream`（chunk）/ `batch`（并行）
- 工具调用五件套：`bind_tools` → `tool_calls` → 手动循环 → `ToolMessage` 回填 → 再 invoke
- 强制调用：`tool_choice="any"` 或指定工具名
- 结构化输出四形态：Pydantic / TypedDict+Annotated / JSON Schema(`method="json_schema"`) / `include_raw=True`
- 高级主题重点：`model.profile`、reasoning 块、`InMemoryRateLimiter`、`openai_proxy`、logprobs（≤0）、token 两种统计、`RunnableConfig`、可配置模型（`configurable_fields` + `config_prefix`）

**Messages**

- 四类消息：`SystemMessage` / `HumanMessage` / `AIMessage` / `ToolMessage`
- 三种写法：对象 / 字符串（单个 Human 的语法糖）/ 字典
- `AIMessage` 六个属性：`text`、`content`、`content_blocks`、`tool_calls`、`usage_metadata`、`response_metadata`
- `AIMessageChunk` 可相加成完整消息，这是流式工具调用拼接的基础
- `ToolMessage.tool_call_id` 必须匹配；`artifact` 不发给模型但代码可读
- content 三形态：字符串 / 厂商原生块 / LangChain 标准块；`content_blocks=` 可用于初始化
- 标准块覆盖：文本、推理、四种多模态、三种工具调用、三种服务端工具、`non_standard` 逃生舱
- 多模态三种来源：`url` / `base64`+`mime_type` / `file_id`
