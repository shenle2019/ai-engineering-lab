"""阶段 5（对应 day06 后半）：MCP 工具接入 + 人机交互（HITL）。

验证点：
1. MCP：FastMCP 数学服务端（stdio）通过 MultiServerMCPClient.get_tools()
   适配成 LangChain 工具，直接交给 create_agent，Agent 代码零改动
2. HITL：退款工具命中 interrupt，打印中断载荷；approve 后工具真正执行
3. HITL：同一 Agent 换线程走 reject 分支，工具不执行，模型给出拒绝后答复

运行：python -m stages.s05_mcp_hitl
"""
import asyncio
import sys
from pathlib import Path

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from lib.llm import deepseek

ROOT = Path(__file__).resolve().parent.parent

# Windows 控制台默认 GBK，模型回复里的 emoji 会导致 UnicodeEncodeError
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


async def part1_mcp() -> None:
    print("=" * 20, "1. MCP：stdio 服务端工具接入", "=" * 20)
    from langchain_mcp_adapters.client import MultiServerMCPClient

    client = MultiServerMCPClient(
        {
            "math": {
                "transport": "stdio",
                "command": sys.executable,
                "args": [str(ROOT / "mcp_server" / "math_server.py")],
            }
        }
    )
    tools = await client.get_tools()
    print(f"[MCP] get_tools() 拿到 {len(tools)} 个工具: {[t.name for t in tools]}")

    agent = create_agent(
        model=deepseek(temperature=0),
        tools=tools,
        system_prompt="你是计算助手，必须用 MCP 工具计算，不要心算。",
    )
    result = await agent.ainvoke({"messages": [{"role": "user", "content": "用工具算 (23+19)*7"}]})
    for m in result["messages"]:
        if getattr(m, "tool_calls", None):
            print(f"[MCP] 调用 {[c['name'] for c in m.tool_calls]}")
        elif m.type == "tool":
            print(f"[MCP] 工具返回 {m.content}")
        elif m.type == "ai" and m.content:
            print(f"[MCP] 最终回答 {m.content}")


REFUND_CALLS: list[str] = []


@tool
def query_order(order_id: str) -> str:
    """查询订单金额与状态。

    Args:
        order_id: 订单号
    """
    return f"订单 {order_id}：金额 268 元，已签收"


@tool
def refund(order_id: str, amount: int) -> str:
    """发起退款（危险操作，需要人工审批）。

    Args:
        order_id: 订单号
        amount: 退款金额（元）
    """
    REFUND_CALLS.append(f"{order_id}:{amount}")
    return f"已退款 {amount} 元到原支付账户（订单 {order_id}）"


def build_hitl_agent():
    return create_agent(
        model=deepseek(temperature=0),
        tools=[query_order, refund],
        system_prompt="你是售后客服。用户要退款时先查订单，再调 refund 发起退款。",
        middleware=[
            HumanInTheLoopMiddleware(
                interrupt_on={"refund": {"allowed_decisions": ["approve", "reject"]}},
                description_prefix="[安全审查] 待批准的操作:",
            )
        ],
        checkpointer=InMemorySaver(),  # HITL 必须配 checkpointer 才能恢复
    )


def show_interrupt(result) -> None:
    interrupts = result.get("__interrupt__") or []
    for item in interrupts:
        value = getattr(item, "value", item)
        requests = value.get("action_requests") if isinstance(value, dict) else None
        print(f"[中断] 载荷: {str(requests)[:200]}")


def part2_hitl_approve() -> None:
    print("=" * 20, "2. HITL：approve 分支", "=" * 20)
    agent = build_hitl_agent()
    config = {"configurable": {"thread_id": "refund-approve"}}
    result = agent.invoke({"messages": [{"role": "user", "content": "订单 A1001 我不想要了，退款 268 元"}]}, config=config)
    show_interrupt(result)
    print(f"[中断] 工具是否已执行: {REFUND_CALLS}")

    final = agent.invoke(Command(resume={"decisions": [{"type": "approve"}]}), config=config)
    print(f"[批准后] 工具执行记录: {REFUND_CALLS}")
    print(f"[批准后] 最终回答: {final['messages'][-1].content}")


def part3_hitl_reject() -> None:
    print("=" * 20, "3. HITL：reject 分支", "=" * 20)
    agent = build_hitl_agent()
    config = {"configurable": {"thread_id": "refund-reject"}}
    before = list(REFUND_CALLS)
    result = agent.invoke({"messages": [{"role": "user", "content": "帮我给订单 A1002 退款 100 元"}]}, config=config)
    show_interrupt(result)
    final = agent.invoke(Command(resume={"decisions": [{"type": "reject"}]}), config=config)
    print(f"[拒绝后] 新增工具执行记录: {REFUND_CALLS[len(before):]} <- 应为空")
    print(f"[拒绝后] 最终回答: {final['messages'][-1].content}")


async def main() -> None:
    await part1_mcp()
    part2_hitl_approve()
    part3_hitl_reject()


if __name__ == "__main__":
    asyncio.run(main())
