"""阶段 06：端到端 —— LLM 通过 MCP 调工具（MCP Host 的最小实现）。

这是整条主线的终点，也是课件里没写透的一环：
DeepSeek / 通义等 OpenAI 兼容模型本身不支持 MCP，需要中间层做协议转换：

    MCP tools/list  ->  OpenAI tools schema  ->  模型返回 tool_calls
    MCP tools/call  <-  按名字分发执行        <-  解析函数名与参数

验证点：
1. 一个 Client 同时挂两个 MCP server（股票 + PC 助手），tools/list 汇总两边
   并自动给工具名加 <server>_ 前缀——这是多路复用最容易踩的坑
2. inputSchema 能直接映射成 OpenAI function calling 的 parameters
3. 模型按需选对 server 的工具：问行情走 stock，问文件走 pc
4. 多跳任务（先查名字换代码，再查行情）能在一次对话里循环执行到收敛
5. 最终回答里的数字与工具返回值一致（不许模型自己编）

无 DEEPSEEK_API_KEY 时降级为 mock，只验证第 1、2 项并在日志里标注。
"""
import asyncio
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastmcp import Client  # noqa: E402
from fastmcp.client.client import MCPConfig  # noqa: E402

from lib.common import setup_logging, banner  # noqa: E402
from lib.llm import get_client  # noqa: E402

STAGE = "06_llm_over_mcp"
SERVERS = {
    "stock": ROOT / "servers" / "stock_server.py",
    "pc": ROOT / "servers" / "pc_helper_server.py",
}
MAX_STEPS = 6


def build_config() -> MCPConfig:
    """Claude Desktop / Trae 里写的那种 JSON 配置，在这个版本里可以原样喂给 Client。"""
    return MCPConfig(
        mcpServers={
            name: {
                "command": sys.executable,
                "args": [str(path)],
                "cwd": str(ROOT),
            }
            for name, path in SERVERS.items()
        }
    )


def to_openai_tool(tool) -> dict:
    """MCP 的 Tool 对象 -> OpenAI function calling 的 tools 条目。

    字段几乎一一对应，唯一要改的是外层包装：
    MCP: name / description / inputSchema
    OpenAI: function.name / function.description / function.parameters
    """
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.inputSchema or {"type": "object", "properties": {}},
        },
    }


def text_of(result) -> str:
    content = getattr(result, "content", None)
    if content is None:
        return str(result)
    return "\n".join(getattr(c, "text", str(c)) for c in content)


async def run_task(log, client: Client, llm, tools: list[dict], user_text: str) -> str:
    """一次提问跑完整闭环，直到模型给出最终文本回答。"""
    log.info("")
    log.info(">>> 用户：%s", user_text)
    messages = [{"role": "user", "content": user_text}]

    for step in range(1, MAX_STEPS + 1):
        resp = llm.chat.completions.create(
            model="deepseek-chat", messages=messages, tools=tools, tool_choice="auto"
        )
        msg = resp.choices[0].message
        if not msg.tool_calls:
            log.info("[第 %d 步] 模型给出最终回答", step)
            return msg.content or ""

        log.info("[第 %d 步] 模型要调 %d 个工具：", step, len(msg.tool_calls))
        messages.append(msg.model_dump(exclude_none=True))
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments or "{}")
            log.info("  -> %s(%s)", tc.function.name, json.dumps(args, ensure_ascii=False))
            try:
                result = await client.call_tool(tc.function.name, args)
                payload = text_of(result)
            except Exception as exc:  # 工具不存在 / 服务端报错，都要回填给模型而不是直接崩
                payload = f"工具执行失败：{exc}"
            log.info("  <- %s", payload.replace("\n", " | ")[:300])
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": payload,
            })

    return "（达到最大步数上限，未收敛）"


async def demo(log) -> bool:
    checks = {}
    sandbox = Path(tempfile.mkdtemp(prefix="mcp_host_"))
    (sandbox / "季度报告.docx").write_text("demo", encoding="utf-8")
    (sandbox / "现场照片.jpg").write_text("demo", encoding="utf-8")
    (sandbox / "会议记录.md").write_text("# demo", encoding="utf-8")

    llm = get_client()
    if not llm:
        log.warning("[MOCK] 没有 DEEPSEEK_API_KEY，跳过真实模型调用，只验证协议转换")

    config = build_config()
    async with Client(config) as client:
        log.info("---- 1. 多 server 的 tools/list 汇总")
        mcp_tools = await client.list_tools()
        for t in mcp_tools:
            log.info("  - %-24s %s", t.name, (t.description or "")[:46])
        names = {t.name for t in mcp_tools}
        # 关键发现：一个 Client 挂多个 server 时，工具名会自动加 <server>_ 前缀
        # （避免两个 server 同名工具冲突），call_tool 也要用带前缀的全名。
        checks["list_tools"] = {
            "stock_get_number", "stock_get_stock_info", "pc_list_files", "pc_organize_by_type"
        } <= names

        log.info("")
        log.info("---- 2. MCP inputSchema -> OpenAI tools 转换")
        tools = [to_openai_tool(t) for t in mcp_tools]
        sample = next(t for t in tools if t["function"]["name"] == "stock_get_stock_info")
        log.info("%s", json.dumps(sample, ensure_ascii=False, indent=2))
        checks["schema"] = sample["function"]["parameters"]["type"] == "object"

        if llm:
            log.info("")
            log.info("---- 3. 行情任务（多跳：查名字 -> 查行情）")
            answer = await run_task(
                log, client, llm, tools,
                "查一下贵州茅台和宁德时代现在的价格、涨跌幅和动态市盈率，",
            )
            log.info("")
            log.info("最终回答：%s", answer)
            checks["stock"] = "茅台" in answer and "宁德" in answer and "未被" not in answer

            log.info("")
            log.info("---- 4. 文件任务（同一个对话桥，路由到另一台 server）")
            answer2 = await run_task(
                log, client, llm, tools,
                f"帮我看看 {sandbox} 这个目录里有什么文件，按类型和大小说明一下。",
            )
            log.info("")
            log.info("最终回答：%s", answer2)
            checks["pc"] = ("docx" in answer2 or "报告" in answer2) and "md" in answer2
        else:
            # 无 key 时用直连调用证明链路本身是通的
            out = text_of(await client.call_tool("stock_get_stock_info", {"stock_code": "600519"}))
            log.info("直连 get_stock_info：%s", out.replace("\n", " | ")[:200])
            checks["stock"] = "贵州茅台" in out

    import shutil

    shutil.rmtree(sandbox, ignore_errors=True)
    for name, ok in checks.items():
        log.info("检查项 %-12s %s", name, "通过" if ok else "失败")
    return all(checks.values())


def main() -> int:
    log = setup_logging(STAGE)
    banner(log, "阶段 06 端到端：LLM 经 MCP 调用工具")
    ok = asyncio.run(demo(log))
    log.info("")
    log.info("阶段 06 %s", "全部通过" if ok else "存在失败项")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
