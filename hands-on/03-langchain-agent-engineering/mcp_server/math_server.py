"""FastMCP 数学服务端（stdio 传输）。

客户端（stages/s05_mcp_hitl.py）会把这个文件当子进程启动，
通过标准输入输出走 MCP 协议。

单独运行（streamable-http 模式）：
    python mcp_server/math_server.py --http
"""
import sys

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("math-service")


@mcp.tool()
def add(a: int, b: int) -> int:
    """两数相加。"""
    return a + b


@mcp.tool()
def multiply(a: int, b: int) -> int:
    """两数相乘。"""
    return a * b


if __name__ == "__main__":
    transport = "streamable-http" if "--http" in sys.argv else "stdio"
    mcp.run(transport=transport)
