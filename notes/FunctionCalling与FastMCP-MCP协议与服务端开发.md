# Function Calling 与 FastMCP：MCP 协议与服务端开发

> 来源：python 山顶会三期 day01（functionCalling 之 AI 股票小助手和 MCP）、day02（FastMCP 从入门到精通）
> 定位：理解向笔记，记录机制、要点与踩坑，不复刻完整代码；案例只记结构与关键细节

## 0. 主线：从"能说话"到"能干活"

大模型只会生成文本，不知道今天的股价、也开不了你的文件夹。让它干活要解决一件事：**模型如何调用外部工具**。这条线的演进：

```
LLM 只会说话
   │  要查实时股票/发邮件/控制电脑
   ▼
Function Calling（手动挡，2023.6 OpenAI 提出）
   │  每个工具写一份 JSON 说明书，每个模型各注册一遍
   ▼
MCP（自动挡，2024.11 Anthropic 提出）
   │  协议统一：工具发布成 server，任何客户端即插即用
   ▼
FastMCP（服务端框架）
   │  Python 写 MCP server 的事实标准
   ▼
三种客户端接入：代码调用（FastMCP Client） / AI 编辑器（Trae） / 大模型直挂（OpenAI responses API）
```

两个概念的关系一句话说清：**MCP 不是取代 Function Calling，而是对它的统一和升级**。模型底层仍然是"看工具说明书→返回函数名和参数"那套 Function Calling 机制，MCP 统一的是"工具怎么被发现、怎么被调用"这一层。MCP 出现后 Function Calling 就淘汰了的说法是错的，没有 Function Calling，MCP 也跑不起来。

## 1. Function Calling：手动挡

### 1.1 七步流程

1. **定义外部函数**：自己写的工具，如查询天气、查询股票、发邮件
2. **写说明书 tools**：严格的 JSON Schema 格式，告诉模型有哪些工具可用
3. **调用大模型**：请求里带上 `tools`
4. **模型决策**：返回要调用的函数名、参数，以及一个 `tool_calls` 的 id
5. **我们自己调用函数**：按模型给的名字和参数执行——MCP 统一的就是这一步
6. **结果回传**：把函数结果以 `role=tool` 的消息塞回对话
7. **模型总结**：模型拿着结果分析推理，输出自然语言答案

### 1.2 说明书 tools 的结构

```
tools = [{
  "type": "function",
  "function": {
    "name": "get_KFC",
    "description": "查询肯德基门店，根据输入的城市名称，查询对应城市的肯德基门店",
    "parameters": {
      "type": "object",
      "properties": {
        "location": {"type": "string", "description": "城市名称，输入中国城市中文名"}
      },
      "required": ["location"]
    }
  }
}]
```

关键认知：**description 写得好不好，直接决定模型选不选这个工具、参数造得对不对**。它不是注释，是给模型看的接口文档。参数描述里能举例就举例（如 `"如'北京','上海'"`）。

### 1.3 反射调用：把字符串变成函数

模型返回的是函数名字符串，不能直接执行，要用映射表反射：

```
available_functions = {"get_KFC": get_KFC}
function_to_call = available_functions[function_name]   # 先查表拿真函数
result = function_to_call(**json.loads(arguments))      # 参数展开后调用
```

这个"名字→函数"映射表（FUNCTION_MAP）是所有智能体项目的固定套路。

### 1.4 第二次请求的消息结构（最容易错的地方）

只把函数结果追加进 messages 是不够的，必须是下面三条齐全：

```
messages = [
  {"role": "user", "content": "帮我查上海地区的肯德基门店"},
  assistant 的 tool_calls 消息（原样放回，含 id/name/arguments）,
  {"role": "tool", "content": 函数返回结果, "tool_call_id": 对应的 tool_calls id}
]
```

漏掉中间那条 assistant 消息或 `tool_call_id` 对不上，模型会重复调用同一个工具、或者直接报错。代码里就是 `messages.append(response_message.model_dump())` 之后追加 tool 消息，再发第二次请求。

### 1.5 模型无关性

Function Calling 的调用协议是 OpenAI 定义的，国内模型（千问、DeepSeek）、本地 ollama 都按兼容模式实现。所以换模型基本只改 `.env`：

```
BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1   # 千问兼容模式
# BASE_URL=http://localhost:11434/v1                          # 本地 ollama
API_KEY=...
MODEL_NAME=qwen-plus
```

注意：小而老的模型可能不支持 tools（如 1.5B 级别的推理模型），换模型后功能失灵先怀疑这点。

## 2. MCP：协议层

### 2.1 概念与时间线

MCP = Model Context Protocol（模型上下文协议），Anthropic 2024 年 11 月提出。类比：以前手机充电口有 Type-C、Lightning、大圆口，MCP 就是那个"都改用 Type-C"的标准——工具不管是官方写的、第三方写的、效率高的、效率低的，调用方式统一。

| 时间 | 技术 | 特点 |
| --- | --- | --- |
| 2023.6 | Function Calling（OpenAI） | 模型可调用预定义函数 |
| 2023 下 | LangChain / Dify 支持工具 | 可视化配置工具 |
| 2024.11 | MCP 协议提出（Anthropic） | 工具标准化、自动发现 |

有了 MCP 之后，12306、高德、支付宝这些厂商自己发布 server，我们不用重写工具，直接调用即可——这是它最大的价值。

### 2.2 C/S 架构与五个术语

| 术语 | 含义 |
| --- | --- |
| MCP Host | 承载大模型的应用：Trae、Cursor、VSCode、自研的股票小助手 |
| MCP Client | 与 server 保持 1:1 连接的协议客户端 |
| MCP Server | 轻量程序，通过标准协议公开特定功能（工具/资源/提示） |
| Local Data Sources | server 可安全访问的本机文件、数据库、服务 |
| Remote Services | server 能连接的外部系统 API |

我们自己会写两端：在高德这类公司做的是 **server 端**（对外提供工具）；做智能体开发用的是 **client 端**（消费别人的 server）。

### 2.3 三种传输方式

| 特性 | Streamable HTTP | Stdio | SSE（已弃用） |
| --- | --- | --- | --- |
| 连接方式 | HTTP 流式请求 | 本地进程 stdin/stdout 管道 | HTTP 长连接，双端点 |
| 需要网络 | 是 | 否 | 是 |
| 部署位置 | 远程服务器/云/本地 | 仅本机 | 远程服务器 |
| 端点数量 | 1 个（如 `/mcp`） | 无（进程直连） | 2 个（`/sse` + `/message`） |
| 生命周期 | 手动启停 | 自动（客户端退出即关） | 手动 |
| 推荐度 | **生产首选** | **本地开发首选** | 不推荐 |

- **Streamable HTTP**：单端点处理所有请求，分块传输编码实现流式；兼容反向代理和防火墙；同时支持"请求-响应"和"持续推送"两种模式。Dify、Cursor、Trae 都优先支持。
- **Stdio**：客户端把 server 当子进程拉起，内存级通信，零网络零配置，数据不过网卡最安全；缺点是只能本机、每个客户端各起一个进程。
- **SSE**：早期方案，双端点设计复杂、易被企业防火墙切断，官方 2025 年起标记弃用（v1.2 deprecated），新项目一律用 streamable-http。

### 2.4 生态入口

| 平台 | 地址 |
| --- | --- |
| 官方 servers 仓库 | github.com/modelcontextprotocol/servers |
| 官方注册中心 | registry.modelcontextprotocol.io |
| 魔塔 MCP 广场（国内） | modelscope.cn/mcp |
| MCP.so | mcp.so/zh |
| MCP Market | mcpmarket.com/zh |
| 百炼 MCP 市场（阿里系工具多） | bailian.console.aliyun.com 里的 MCP 市场 |

厂商发布的 server 代码大多开源、数据不开源（数据才是核心资产）。Python 写 MCP 用官方 SDK 较繁琐，**FastMCP 被官方推荐为标准框架**。

### 2.5 第三方 server 实战：12306 查票

```
git clone https://github.com/Joooook/12306-mcp.git     # 一个 Node 写的社区 server
cd 12306-mcp && docker build . -t 12306-mcp            # 基于 node:lts-alpine 构建
docker run -p 8080:8080 -d 12306-mcp npx 12306-mcp --port 8080
```

部署到云服务器后，在 Trae 里配置客户端 JSON 即可用自然语言查票。两个坑：

- **Trae 新旧版本端点不同**：老版本填 `http://IP:8080/mcp`，新版本填 `http://IP:8080/sse`
- 云服务器**安全组要放行端口**，否则外面连不上

## 3. FastMCP：服务端开发

### 3.1 安装与版本

```
pip install "fastmcp<3"     # 装 2.x 最新版；裸装 pip install fastmcp 会到 3.x
fastmcp version
```

版本脉络：FastMCP 1.0 于 2024 年被并入官方 MCP Python SDK；FastMCP 2.0 是独立维护的生产级框架，在 SDK 核心之上补了 server 组合、代理、OpenAPI 生成、企业认证、部署与测试工具。Python 推荐 3.12（3.13 部分依赖支持不佳）。

### 3.2 最小服务端

```
from fastmcp import FastMCP

mcp = FastMCP("我们自己的MCPserver")

@mcp.tool
def add(a: int, b: int) -> int:
    return a + b + 100

if __name__ == "__main__":
    mcp.run(transport="http")     # 默认是 stdio
```

两种启动方式：右键运行，或命令行 `fastmcp run server.py:mcp --transport http --port 8000`。

**认知纠偏**：浏览器直接打开 `http://127.0.0.1:8000/mcp` 会看到报错，这是正常的——那是 MCP 协议端点，只接受 MCP 客户端请求，不是普通网页/接口。

### 3.3 三大组件：Tool / Resource / Prompt

一句话记法：**要"动"用 Tool，要"知"用 Resource，要"说"用 Prompt。**

| 组件 | 定义 | 有无副作用 | 关键词 | 典型场景 |
| --- | --- | --- | --- | --- |
| Tool | 可执行函数，收结构化输入返结构化输出 | 允许（可改状态） | Do something | 发消息、下单、控制 IoT、删文件 |
| Resource | 只读数据源，给模型提供上下文 | 无副作用 | Know something | RAG 检索、注入用户偏好、只读访问敏感数据 |
| Prompt | 服务端管理的参数化消息模板 | 无 | Say something in a specific way | 报告模板、邮件草稿、强制免责声明 |

**Tool**：`@mcp.tool(name=..., description=..., tags={...}, meta={...})`，函数签名和类型注解会被自动转成 JSON Schema 说明书——这就是 Function Calling 里手写的 tools，FastMCP 帮你生成了。

**Resource**：用 URI 区分，支持自定义 scheme 和 file 方案：

```
@mcp.resource("resource://greeting")        # 返回 str
@mcp.resource("data://config")              # 返回 dict，自动序列化成 JSON
@mcp.resource("file:///path/to/README.md", mime_type="text/markdown")
def get_md() -> FileResource:               # 静态文件用 FileResource(uri, path, name, description, mime_type, tags)
```

客户端侧 `list_resources()` 拿清单、`read_resource(uri)` 拿内容，文本走 `.text`、二进制走 `.blob`。

**Prompt**：`@mcp.prompt` 装饰的函数，返回 str 会自动转成 user 消息，也可以返回 `PromptMessage(role=..., content=TextContent(...))` 做精细控制。客户端 `get_prompt(name, {参数})` 取渲染后的消息。

三者协作的经典例子——"给 lqz 发一封今日新闻总结邮件"：

```
Resource user_profile → 拿到邮箱
Resource latest_news  → 拿到新闻原文
Prompt   总结新闻模板  → 渲染出摘要草稿
Tool     send_email   → 真正发出去
```

### 3.4 中间件

MCP 中间件能在请求"进来"和"出去"两个时机统一处理逻辑，所有请求都会经过：

```
class LoggingMiddleware(Middleware):
    async def on_message(self, context: MiddlewareContext, call_next):
        start = time.time()
        result = await call_next(context)      # 进入业务
        print(context.method, time.time() - start)
        return result

mcp.add_middleware(LoggingMiddleware())
```

常见用途：身份验证与授权、日志与监控、速率限制、请求/响应改写、缓存、统一错误处理。

### 3.5 客户端三种接入方式

**方式一：FastMCP Client（代码调用）**

```
client = Client("http://127.0.0.1:8000/mcp")

async def main():
    async with client:
        tools = await client.list_tools()                 # 自动拿到说明书
        result = await client.call_tool("add", {"a": 3, "b": 4})
        print(result.structured_content)
```

除了 `list_tools/call_tool`，还有 `list_resources/read_resource`、`list_prompts/get_prompt`。相比 Function Calling，本地代码里"注册说明书"这一步没了——由 server 自动暴露。

**方式二：AI 编辑器配置（Trae/Cursor/VSCode）**

```
{"mcpServers": {"add": {"url": "http://127.0.0.1:8000/mcp"}}}
```

配好后用自然语言提需求，编辑器的大模型会自己发现并调用工具。Pycharm 最新版官方尚不支持 MCP 客户端。

**方式三：OpenAI SDK 直挂 MCP（过渡方案）**

```
response = client.responses.create(
    model=..., 
    tools=[{"type": "mcp", "server_label": "dice_server",
            "server_url": "http://127.0.0.1:8000/mcp",
            "require_approval": "never"}])
```

把 MCP server 直接写进模型的 tools 参数，模型自己完成发现与调用，本地不用写 client 代码。目前绝大多数模型还不支持（国产和 OpenAI 标准接口都不行），FastMCP 先提供 SDK 能力，属于前瞻方向。

**多 server 的情况**：同一服务端可以放多个 MCP server，但功能别重复——多个 server 多个工具时，大模型会自由选择，一个失败会换另一个重试，功能重叠只会增加不确定性。

## 4. 案例一：AI 股票小助手（Function Calling 主线）

### 4.1 结构

```
用户提问 → 千问 qwen-plus → 决定调用 get_number / get_stock_info
        → 我们自己执行 → 结果回传模型 → 中文简洁回答
```

两个工具：

| 工具 | 作用 | 实现要点 |
| --- | --- | --- |
| `get_number(name)` | 公司名 → 股票代码 | 本地字典映射 12 只股票；查不到兜底返回 600519（这是刻意留的教学缺陷，生产应改查询接口） |
| `get_stock_info(code)` | 代码 → 实时行情 | 调东方财富 `push2.eastmoney.com/api/qt/stock/get?secid=` |

### 4.2 东方财富接口的关键细节

- **secid 规则**：沪市（6 开头，含科创板）用 `1.600519`，深市（0/3 开头）用 `0.002594`；代码里就是 `f"1.{code}" if code.startswith("6") else f"0.{code}"`
- **返回字段**：`f58` 名称、`f43` 现价（**除以 1000**）、`f170` 涨跌幅（**除以 100** 得百分比）、`f116` 市盈率
- `rc != 0` 表示查询失败；`f43` 为空多半是停牌

### 4.3 三层外壳

- **core.py**：`client.chat.completions.create(model, messages, tools, tool_choice="auto")`；取 `tool_calls[0]` 反射执行；结果追加"股市有风险，投资需谨慎"免责声明后直接返回
- **terminal.py**：命令行死循环，system 提示词约束"只查 A 股实时行情"，messages 跨轮累积
- **flask_run.py**：`/` 渲染聊天页，`/chat` POST 接 query 调 core 返回 JSON；注意每轮重新构造 messages，没有多轮上下文

### 4.4 上线

Dockerfile：`python:3.11` + 清华 pypi 源 + `EXPOSE 8080` + `CMD ["python", "flask_run.py"]`；compose 单服务映射 8080:8080。服务器装 Docker 三步：加阿里云 docker-ce 源（dnf）→ 配 `daemon.json` 的 registry-mirrors（如 `https://docker.1ms.run`）→ `systemctl restart docker`。

### 4.5 扩展套路

做新的智能体只动三处：定义工具函数 → 写 tools 说明书 → 注册 FUNCTION_MAP。其余代码（客户端、循环、Web 外壳）全部复用。换成 MCP 后第一、二步由 server 承担，client 只负责 `call_tool`。

## 5. 案例二：AI PC 助手（FastMCP 主线）

### 5.1 四个工具

| 工具 | 功能 | 实现要点 |
| --- | --- | --- |
| `list_files_in_directory(path)` | 列出目录下文件名/类型/字节/可读大小 | `Path.resolve()` 校验存在与是否目录；`PermissionError` 单独捕获 |
| `organize_files_by_type(target_dir)` | 按扩展名整理到 `YYYYMMDD_ext` 文件夹 | 只处理顶层不递归；`shutil.move`；目标已存在则跳过不覆盖 |
| `list_all_software()` | 列出已安装软件 | 仅 Windows，走注册表 |
| `uninstall_by_exact_name(name)` | 按名称启动卸载程序 | 精确匹配（转小写比较），`subprocess.run(cmd, shell=True)` 拉起卸载向导 |

### 5.2 读注册表的通用套路（utils.py）

用 subprocess 调 PowerShell 读两个注册表位置：`HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*` 和 `Wow6432Node` 下的同名路径（32 位程序在这），筛出 `DisplayName` 和 `UninstallString`，`ConvertTo-Json -Compress` 后 Python 侧 `json.loads`。注意：PowerShell 输出单个对象时是 dict 不是 list，要统一处理；`timeout=45` 防卡死。

### 5.3 这个案例真正的价值

MCP server 能做的事，边界就是**启动它的客户端的权限**——因为 server 是客户端拉起的本地进程，所以能读写本机文件、调注册表、拉起卸载程序。业务员能问"电脑上装了什么软件、帮我卸载 Pycharm"，AI 就能通过 MCP 真的动手。这也说明 MCP 的安全边界：server 权限 = 宿主权限，别把未知 server 随便接进来（对应 day02 开头"卸载软件：控制不能卸载 Pycharm"的演示）。

### 5.4 已知缺陷（读代码时注意）

- `uninstall_by_exact_name` 找不到软件时 `target = None` 直接解包，会抛异常而不是返回友好提示
- 只支持精确匹配，名字差一个空格就查不到
- `organize_files_by_type` 不递归子目录，多层目录会留一半没整理

## 6. 踩坑清单

1. **浏览器打开 `/mcp` 报错是正常的**——MCP 端点只认协议客户端，别去改代码
2. **第二次请求必须带回 assistant 的 tool_calls 消息 + `tool_call_id`**，否则模型反复调工具或直接报错
3. **tool 的 description 就是给模型看的接口文档**，写含糊模型就乱选工具、乱造参数
4. **Trae 新旧版本 MCP 端点不同**：老版 `/mcp`、新版 `/sse`；Pycharm 暂不支持 MCP 客户端
5. **别提供功能重复的多个 server**：模型会自由选择并失败重试，结果不可控
6. **小模型可能不支持 tools**：换 ollama 本地小模型后 function calling 失效，先查模型能力
7. **云服务器安全组要放行端口**，否则远程客户端连不上
8. **API_KEY 只进 `.env`**，不写进代码不提交仓库；课件里出现的 key 一律不复用
9. **`fastmcp run` 要写 `server.py:mcp`**，冒号后面是 FastMCP 实例的变量名
10. **Windows 路径权限**：遍历目录先 `resolve()` 再判断，`PermissionError` 单独兜底

## 7. 速查表

| 用途 | 写法 |
| --- | --- |
| 安装 | `pip install "fastmcp<3"` |
| 启动 server | `mcp.run(transport="http")` / 命令行 `fastmcp run server.py:mcp --transport http --port 8000` |
| 定义工具 | `@mcp.tool(name=..., description=...)` + 类型注解 |
| 定义资源 | `@mcp.resource("data://config")`，文件用 `FileResource` |
| 定义提示 | `@mcp.prompt`，返回 str 或 `PromptMessage` |
| 挂中间件 | `mcp.add_middleware(LoggingMiddleware())` |
| 客户端调用 | `async with Client(url): await client.call_tool(name, args)` |
| Trae 配置 | `{"mcpServers": {"名字": {"url": "http://127.0.0.1:8000/mcp"}}}` |
| 东方财富行情 | `push2.eastmoney.com/api/qt/stock/get?secid=1.600519`（6 开头 1.、其余 0.） |
