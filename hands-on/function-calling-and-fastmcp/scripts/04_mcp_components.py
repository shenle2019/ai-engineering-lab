"""阶段 04：验证 FastMCP 的 resource / prompt 组件与中间件证据。

前置：阶段 03 已经验证 tool。
验证点：
1. list_resources 能发现 data://stock_codes，read_resource 拿到 JSON 内容
2. list_prompts 能发现 stock_review，get_prompt 渲染出带参数的消息
3. 中间件把每次调用的方法名与耗时写进 logs/server_middleware.log
   —— 这证明"所有请求都会经过中间件"，也解决 stdio 模式下看不到 server 日志的问题
"""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastmcp import Client  # noqa: E402

from lib.common import setup_logging, banner, LOG_DIR  # noqa: E402

STAGE = "04_mcp_components"
SERVER = ROOT / "servers" / "stock_server.py"
MIDDLEWARE_LOG = LOG_DIR / "server_middleware.log"


async def demo(log) -> bool:
    client = Client(str(SERVER))
    async with client:
        # ---- resource：只读数据 ----
        resources = await client.list_resources()
        log.info("list_resources 发现 %d 个资源：", len(resources))
        for res in resources:
            log.info("  - uri=%s name=%s mime=%s", res.uri, res.name, res.mimeType)

        content = await client.read_resource("data://stock_codes")
        text = content[0].text if hasattr(content[0], "text") else str(content[0])
        log.info("read_resource 内容（前 160 字）：%s", text[:160].replace("\n", " "))
        ok_resource = "600519" in text and "贵州茅台" in text

        # ---- prompt：参数化模板 ----
        prompts = await client.list_prompts()
        log.info("list_prompts 发现 %d 个提示：", len(prompts))
        for p in prompts:
            log.info("  - name=%s args=%s", p.name, [a.name for a in (p.arguments or [])])

        prompt = await client.get_prompt("stock_review", {"topic": "贵州茅台"})
        msg = prompt.messages[0]
        rendered = msg.content.text if hasattr(msg.content, "text") else str(msg.content)
        log.info("get_prompt 渲染结果：%s", rendered)
        ok_prompt = "贵州茅台" in rendered and "get_stock_info" in rendered
        return ok_resource and ok_prompt


def main() -> int:
    log = setup_logging(STAGE)
    banner(log, "阶段 04 FastMCP 组件：resource / prompt / 中间件")

    before = MIDDLEWARE_LOG.read_text(encoding="utf-8").count("\n") if MIDDLEWARE_LOG.exists() else 0
    ok = asyncio.run(demo(log))

    after_lines = MIDDLEWARE_LOG.read_text(encoding="utf-8").splitlines() if MIDDLEWARE_LOG.exists() else []
    new_lines = after_lines[before:]
    log.info("")
    log.info("中间件本次新增 %d 条记录：", len(new_lines))
    for line in new_lines:
        log.info("  %s", line)
    ok_middleware = len(new_lines) >= 4  # initialize + resources/list + resources/read + prompts/list + prompts/get

    log.info("")
    log.info("阶段 04 组件=%s 中间件=%s", "通过" if ok else "失败", "通过" if ok_middleware else "失败")
    return 0 if (ok and ok_middleware) else 1


if __name__ == "__main__":
    raise SystemExit(main())
