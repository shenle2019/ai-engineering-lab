"""阶段 03：把股票工具发布成 MCP server，并用两种传输方式调用。

验证点：
1. stdio：客户端把 server 当子进程拉起，list_tools 能自动拿到说明书
2. call_tool 真实执行工具，返回结构化结果（东方财富实时行情）
3. http：server 独立监听端口，客户端走 /mcp 单端点调用
4. 用普通 HTTP 请求打 /mcp 会得到 4xx —— 验证"浏览器直接访问报错是正常的"
"""
import asyncio
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import requests  # noqa: E402
from fastmcp import Client  # noqa: E402

from lib.common import setup_logging, banner  # noqa: E402

STAGE = "03_mcp_basic"
SERVER = ROOT / "servers" / "stock_server.py"
HTTP_PORT = 8765


async def demo_stdio(log) -> bool:
    log.info("---- 方式一：stdio（客户端拉起子进程，零网络） ----")
    client = Client(str(SERVER))
    async with client:
        tools = await client.list_tools()
        log.info("list_tools 自动拿到 %d 个工具：", len(tools))
        for tool in tools:
            log.info("  - %s：%s", tool.name, tool.description)
            log.info("    inputSchema=%s", tool.inputSchema)

        result = await client.call_tool("get_number", {"name": "贵州茅台"})
        log.info("call_tool get_number -> %s", result.data)

        result = await client.call_tool("get_stock_info", {"code": "600519"})
        text = str(result.data)
        log.info("call_tool get_stock_info -> %s", text.replace("\n", " | ")[:200])
        return "贵州茅台" in text and "最新价" in text


def wait_port(port: int, timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket() as sock:
            sock.settimeout(0.5)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.2)
    return False


async def demo_http(log) -> bool:
    log.info("")
    log.info("---- 方式二：Streamable HTTP（单端点 /mcp） ----")
    proc = subprocess.Popen(
        [sys.executable, str(SERVER), "--http", str(HTTP_PORT)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
    )
    try:
        if not wait_port(HTTP_PORT):
            log.error("server 未在端口 %d 就绪", HTTP_PORT)
            return False
        log.info("server 已监听 127.0.0.1:%d", HTTP_PORT)

        client = Client(f"http://127.0.0.1:{HTTP_PORT}/mcp")
        async with client:
            tools = await client.list_tools()
            log.info("HTTP 客户端 list_tools -> %s", [t.name for t in tools])
            result = await client.call_tool("get_stock_info", {"code": "300750"})
            text = str(result.data)
            log.info("call_tool get_stock_info(300750) -> %s", text.replace("\n", " | ")[:160])
            ok = "宁德时代" in text

        # 用普通 HTTP 请求打 /mcp：必须失败，证明它不是普通接口
        resp = requests.get(f"http://127.0.0.1:{HTTP_PORT}/mcp", timeout=5)
        log.info("普通 GET /mcp 返回 HTTP %d（4xx/5xx 即符合预期：MCP 端点不认普通请求）",
                 resp.status_code)
        return ok and resp.status_code >= 400
    finally:
        proc.terminate()
        try:
            out, err = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            out, err = proc.communicate()
        if err:
            tail = [ln for ln in err.splitlines() if "middleware" in ln or "INFO" in ln or "Uvicorn" in ln]
            for line in tail[-5:]:
                log.info("server stderr: %s", line)


def main() -> int:
    log = setup_logging(STAGE)
    banner(log, "阶段 03 MCP server：两种传输方式")
    ok_stdio = asyncio.run(demo_stdio(log))
    ok_http = asyncio.run(demo_http(log))
    log.info("")
    log.info("阶段 03 stdio=%s http=%s", "通过" if ok_stdio else "失败", "通过" if ok_http else "失败")
    return 0 if (ok_stdio and ok_http) else 1


if __name__ == "__main__":
    raise SystemExit(main())
