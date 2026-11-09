"""AI 股票小助手 MCP server（FastMCP）。

一个 server 里放齐四类要素，供阶段 03/04/06 分别验证：
- tool：get_number / get_stock_info（可执行、有外部访问）
- resource：data://stock_codes（只读的公司名→代码表）
- prompt：stock_review（参数化分析模板）
- middleware：记录每次调用的方法名与耗时到 logs/server_middleware.log

启动：
    python servers/stock_server.py            # stdio（默认，供本机客户端拉起）
    python servers/stock_server.py --http 8765  # Streamable HTTP，单端点 /mcp

数据来自东方财富公开行情接口（匿名、只读、低频），仅限学习研究使用。
"""
import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastmcp import FastMCP  # noqa: E402
from fastmcp.server.middleware import Middleware, MiddlewareContext  # noqa: E402

from lib.common import LOG_DIR  # noqa: E402
from lib.eastmoney import NAME_TO_CODE, format_quote, get_number, get_quote  # noqa: E402

mcp = FastMCP(
    name="AI股票小助手",
    instructions=(
        "提供 A 股实时行情查询：用 get_number 把公司名换成 6 位代码，"
        "用 get_stock_info 查最新价、涨跌幅、市盈率、市净率、总市值。"
        "数据来自东方财富公开接口，仅供参考，不构成投资建议。"
    ),
)


class TimingMiddleware(Middleware):
    """记录每次 MCP 调用的方法名与耗时：日志落盘，stdio 模式也能留证据。"""

    async def on_message(self, context: MiddlewareContext, call_next):
        start = time.perf_counter()
        result = await call_next(context)
        elapsed = time.perf_counter() - start
        line = f"{datetime.now().isoformat(timespec='seconds')} {context.method} {elapsed:.3f}s\n"
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with (LOG_DIR / "server_middleware.log").open("a", encoding="utf-8") as fh:
            fh.write(line)
        # stdio 模式下 stdout 属于协议通道，日志只能走 stderr
        print(f"[middleware] {line.strip()}", file=sys.stderr, flush=True)
        return result


mcp.add_middleware(TimingMiddleware())


# ---------------- tool：可执行动作 ----------------
@mcp.tool(name="get_number", description="通过公司中文名查询 6 位股票代码，例如 贵州茅台 -> 600519")
def tool_get_number(name: str) -> str:
    return get_number(name)


@mcp.tool(
    name="get_stock_info",
    description="根据 6 位股票代码查询 A 股实时行情：最新价、涨跌幅、市盈率、市净率、总市值",
)
def tool_get_stock_info(code: str) -> str:
    return format_quote(get_quote(code))


# ---------------- resource：只读数据 ----------------
@mcp.resource("data://stock_codes")
def stock_codes() -> dict:
    """内置的公司名→代码对照表（只读资源）。"""
    return NAME_TO_CODE


# ---------------- prompt：参数化模板 ----------------
@mcp.prompt
def stock_review(topic: str) -> str:
    """生成一只股票的简要分析请求模板。"""
    return (
        f"请调用 get_stock_info 查询 {topic} 的实时数据，然后用三点概括："
        "价格位置、估值水平、风险提示。不要编造数据。"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--http", type=int, default=0, help="以 Streamable HTTP 启动并监听该端口")
    args = parser.parse_args()
    if args.http:
        mcp.run(transport="http", port=args.http)
    else:
        mcp.run()  # 默认 stdio
