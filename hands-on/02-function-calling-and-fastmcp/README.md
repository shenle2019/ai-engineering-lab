# Function Calling 与 FastMCP 实操

把 day01「Function Calling 之 AI 股票小助手和 MCP」和 day02「FastMCP 从入门到精通」两课串成一条链路：
**手工挡（Function Calling 七步）→ 自动挡（MCP server）→ 三种客户端 → LLM 真正经 MCP 调工具**。
不照抄课件代码，按自己的工程习惯重写，并用真实数据与真实模型验证。

## 来源课次

- `python山顶会三期/day01-functionCalling之-AI股票小助手和MCP`
- `python山顶会三期/day02-FastMCP从入门到精通`

## 案例主线

```
东方财富行情接口 ──► lib/eastmoney.py（字段校准后的行情工具）
                          │
        阶段 01           │           阶段 03/04/06
   手工 Function Calling ─┘─► stock_server.py（MCP）─► FastMCP Client / 多 server Host
                          │                                   │
   阶段 02 校准字段        └─► pc_helper_server.py（文件整理）  └─► DeepSeek 决策后回填
```

一条主线两个 case：股票助手（真实行情、多跳调用）和 PC 助手（本机文件操作、安全边界）。

## 运行环境

| 项 | 值 |
| --- | --- |
| OS | Windows 10 22H2 |
| Python | 3.11.9（目录内 `.venv`，系统默认 3.8 跑不了 fastmcp） |
| fastmcp | 2.14.7（`fastmcp<3`） |
| openai / requests / python-dotenv | 3.46.0 / 2.32.x / 1.x |
| LLM | DeepSeek `deepseek-chat`（OpenAI 兼容协议），key 只放环境变量 `DEEPSEEK_API_KEY` |
| 行情数据 | 东方财富公开接口，匿名、只读、低频，仅学习研究使用 |

## 目录结构

```
function-calling-and-fastmcp/
├── lib/
│   ├── common.py          # 日志（同时写控制台与 logs/<stage>.log）
│   ├── eastmoney.py       # 行情工具，字段单位已按实测校准
│   └── llm.py             # DeepSeek 客户端，无 key 返回 None
├── servers/
│   ├── stock_server.py    # MCP server：tool + resource + prompt + middleware
│   └── pc_helper_server.py# MCP server：list_files / organize_by_type
├── scripts/               # 00-06 阶段脚本，每个只验证一个环节
└── logs/                  # 运行日志，作为验证证据
```

## 各阶段验证点与结果

| 阶段 | 验证点 | 结果 |
| --- | --- | --- |
| 00 环境预检 | Python ≥3.10、依赖齐全、行情接口可达、key 可用 | 通过；DeepSeek 最小对话成功 |
| 01 Function Calling | 模型返回结构化 tool_calls、反射执行、两次消息回填、反例 | 通过；3 跳完成「查名 → 查行情 → 总结」；漏掉 assistant 的 tool_calls 消息时接口返回 400 |
| 02 行情字段校准 | 用真实数据核对 f43 除数与 f116 含义 | 通过；发现课件两处错误，见下节 |
| 03 MCP 两种传输 | stdio 子进程 + Streamable HTTP 单端点 `/mcp` | 通过；两种方式都拿到工具并返回真实行情；普通 GET `/mcp` 返回 406 |
| 04 组件与中间件 | resource 可读、prompt 可渲染、中间件记录请求 | 通过；`data://stock_codes`、`stock_review`、5 条中间件日志 |
| 05 PC 助手 | 列文件、按扩展名整理、幂等、拒绝系统目录、非法路径 | 6 项全通过；沙箱验证后自动清理 |
| 06 LLM 经 MCP 调工具 | 多 server 汇总、schema 转换、模型自动选工具、多跳收敛 | 通过；同一 Client 挂 stock+pc，行情与文件任务各自路由正确 |

关键证据（`logs/` 内可复查）：

- 阶段 03：`get_stock_info(600519)` → 1444.99 元 / -0.55% / 动态 PE 21.01 / 总市值 18063.55 亿
- 阶段 06：模型自主先调 `stock_get_number` 再调 `stock_get_stock_info`，最终回答同时覆盖茅台与宁德时代
- 阶段 06：文件任务被路由到 `pc_list_files`，模型正确归纳出 3 个文件、3 种类型

## 运行方式

```powershell
# 0. 准备（只需一次）
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install "fastmcp<3" openai requests python-dotenv
$env:DEEPSEEK_API_KEY = "sk-..."     # 不写进仓库

# 1. 按顺序跑阶段脚本
.\.venv\Scripts\python.exe scripts\00_env_check.py
.\.venv\Scripts\python.exe scripts\01_function_calling.py
.\.venv\Scripts\python.exe scripts\02_eastmoney_calibrate.py
.\.venv\Scripts\python.exe scripts\03_mcp_basic.py
.\.venv\Scripts\python.exe scripts\04_mcp_components.py
.\.venv\Scripts\python.exe scripts\05_pc_helper.py
.\.venv\Scripts\python.exe scripts\06_llm_over_mcp.py

# 2. 单独起 MCP server（接 Trae / Cursor 或 fastmcp CLI）
.\.venv\Scripts\python.exe servers\stock_server.py               # stdio
.\.venv\Scripts\python.exe servers\stock_server.py --http 8765   # http://127.0.0.1:8765/mcp
```

在 Trae / Cursor 里挂这个 server，配置就是标准的 JSON：

```json
{
  "mcpServers": {
    "stock": {
      "command": "E:\\...\\function-calling-and-fastmcp\\.venv\\Scripts\\python.exe",
      "args": ["E:\\...\\function-calling-and-fastmcp\\servers\\stock_server.py"]
    }
  }
}
```

## 与课件的差异（都是实测踩出来的）

1. **`f43` 除数是 100，不是 1000**。课件写 `/1000`，会把茅台算成 144 元。阶段 02 用茅台、宁德两档股价反推确认。
2. **`f116` 是总市值，不是市盈率**。课件注为「市盈率」；总市值要 `/1e8` 转亿元，动态市盈率取 `f162`（`/100`），PE(TTM) 取 `f164`。
3. **每次请求都要带 `tools`**。阶段 01 第一次只在首轮传 tools，DeepSeek 第二次就把调用意图写成 `<｜｜DSML｜｜>` 文本而不是结构化 `tool_calls`。现在统一每轮都传，并循环执行到模型不再调工具。
4. **多 server 汇总时工具名会被加前缀**。一个 `Client` 挂 `stock` + `pc` 后，`get_stock_info` 变成 `stock_get_stock_info`、`list_files` 变成 `pc_list_files`。按原名找工具会 `StopIteration`，`call_tool` 也必须用带前缀的全名。
5. **不做卸载软件工具**。课件 PC 助手有 `uninstall_by_exact_name`（`subprocess` 调 PowerShell 精确匹配卸载）。学习环境没有可安全验证的对象，刻意省略，只保留可逆的文件整理；README 与 server 注释里都写了原因。
6. **不抄课件 `.env`**。仓库里不出现任何 `sk-` 开头的 key，只写变量名。

## 踩坑记录

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| 系统 `python` 是 3.8，装 fastmcp 失败 | fastmcp 要求 ≥3.10 | 用本机 3.11 建 `.venv`，所有命令走 venv 解释器 |
| 第二次请求返回 `<｜｜DSML｜｜>` 文本 | 请求没带 `tools` | 每轮请求都带 tools，并循环到模型不再调用 |
| `role=tool` 请求报 400 | 缺对应的 assistant `tool_calls` 消息 | 先 append `msg.model_dump()`，再 append 工具结果 |
| 浏览器打开 `/mcp` 报错 | 该端点只认 MCP 协议 | 普通 GET 返回 406 是正常现象 |
| 多 server 找不到工具名 | 自动加 `<server>_` 前缀 | 用 `list_tools` 返回的全名调用 |
| PowerShell 控制台中文乱码 | GBK 控制台 vs UTF-8 输出 | 日志文件为 UTF-8，用编辑器查看即可，不影响内容 |

## 可复用的结论

- 换模型只改 `lib/llm.py` 的 base_url / model / key，工具层与 server 层不动——Function Calling 是协议，不是某家模型的特性。
- 想把已有函数发布成 MCP，最小改动就是加 `@mcp.tool` 再 `mcp.run()`；resource 放只读数据、prompt 放话术模板，三者边界按「Do / Know / Say」分。
- LLM 要接 MCP，中间必须有一层协议转换（MCP Host）：`tools/list` → OpenAI tools → 模型 `tool_calls` → `tools/call`。阶段 06 的 `run_task` 就是最小实现。
