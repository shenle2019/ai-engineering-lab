"""阶段 7（对应 day07 后半）：多智能体的两种做法。

验证点：
1. Agent 当工具：主管 Agent 把「售前专家 / 售后专家」两个子 Agent 当工具调用
2. LangGraph 交接：两个 Agent 作为图节点，售前专家用
   Command(goto="aftersale", graph=Command.PARENT) 把会话交给售后专家，
   父图状态里的 active_agent 随之切换

运行：python -m stages.s07_multiagent
"""
import sys

from langchain.agents import AgentState, create_agent
from langchain.tools import ToolRuntime, tool
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command
from typing import NotRequired

from lib.llm import deepseek

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

MODEL = deepseek(temperature=0)


@tool
def query_order(order_id: str) -> str:
    """查询订单状态与金额。

    Args:
        order_id: 订单号
    """
    return f"订单 {order_id}: 金额 268 元，已签收"


# ---------- 做法一：Agent 当工具 ----------
presale_agent = create_agent(
    model=MODEL,
    tools=[],
    system_prompt="你是售前顾问，只回答商品、价格、优惠问题，回答不超过 40 字。",
    name="presale_agent",
)
aftersale_agent = create_agent(
    model=MODEL,
    tools=[query_order],
    system_prompt="你是售后专家，处理退款、物流、投诉，回答不超过 40 字。",
    name="aftersale_agent",
)


@tool("presale_expert", description="售前专家：商品、价格、优惠、下单咨询")
def call_presale(question: str) -> str:
    result = presale_agent.invoke({"messages": [{"role": "user", "content": question}]})
    return result["messages"][-1].content


@tool("aftersale_expert", description="售后专家：退款、退货、物流、投诉")
def call_aftersale(question: str) -> str:
    result = aftersale_agent.invoke({"messages": [{"role": "user", "content": question}]})
    return result["messages"][-1].content


def part1_agent_as_tool() -> None:
    print("=" * 20, "1. Agent 当工具", "=" * 20)
    triage = create_agent(
        model=MODEL,
        tools=[call_presale, call_aftersale],
        system_prompt=(
            "你是客服主管。售前问题交给 presale_expert，售后问题交给 aftersale_expert，"
            "必须调用对应专家，不要自己回答。最后用一句话转述专家结论。"
        ),
    )
    questions = ["你们的 langchain 课多少钱？", "订单 A1001 我想退款，能退多少？"]
    for q in questions:
        result = triage.invoke({"messages": [{"role": "user", "content": q}]})
        called = [c["name"] for m in result["messages"] if getattr(m, "tool_calls", None) for c in m.tool_calls]
        print(f"[问题] {q}")
        print(f"[主管调用的专家] {called}")
        print(f"[最终答复] {result['messages'][-1].content}")


# ---------- 做法二：LangGraph 交接 ----------
class TeamState(AgentState):
    active_agent: NotRequired[str]


@tool
def transfer_to_aftersale(runtime: ToolRuntime[None, TeamState]) -> Command:
    """把会话转交给售后专家（用户提出退款、退货、物流、投诉时使用）。"""
    return Command(
        goto="aftersale",
        graph=Command.PARENT,  # 从子 Agent 图跳回父图
        update={"active_agent": "aftersale"},
    )


presale_node_agent = create_agent(
    model=MODEL,
    tools=[transfer_to_aftersale],
    system_prompt=(
        "你是售前顾问。用户提出退款、退货、物流、投诉时，必须调用 transfer_to_aftersale；"
        "否则直接回答商品问题，40 字以内。"
    ),
    name="presale_node",
)
aftersale_node_agent = create_agent(
    model=MODEL,
    tools=[query_order],
    system_prompt="你是售后专家，处理退款、物流、投诉，回答不超过 40 字。",
    name="aftersale_node",
)


def route_initial(state: TeamState) -> str:
    last = next((m for m in reversed(state["messages"]) if m.type == "human"), None)
    text = str(last.content) if last else ""
    return "aftersale" if any(k in text for k in ("退款", "退货", "物流", "投诉")) else "presale"


def triage_node(state: TeamState) -> Command:
    """入口路由：图节点直接返回 Command，既跳转又把 active_agent 写进状态。"""
    target = route_initial(state)
    print(f"   [triage] 入口路由 -> {target}")
    return Command(goto=target, update={"active_agent": target})


def build_team_graph():
    builder = StateGraph(TeamState)
    builder.add_node("triage", triage_node)
    builder.add_node("presale", presale_node_agent)
    builder.add_node("aftersale", aftersale_node_agent)
    builder.add_edge(START, "triage")
    builder.add_edge("presale", END)
    builder.add_edge("aftersale", END)
    return builder.compile()


def part2_graph_handoff() -> None:
    print("=" * 20, "2. LangGraph 交接（Command + Command.PARENT）", "=" * 20)
    graph = build_team_graph()
    result = graph.invoke({"messages": [{"role": "user", "content": "你们的课程能开发票吗？"}], "active_agent": None})
    print(f"[售前入口] active_agent={result.get('active_agent')}")
    print(f"[售前入口] 回答: {result['messages'][-1].content}")

    result2 = graph.invoke({"messages": [{"role": "user", "content": "课程买了不合适，我要退款"}], "active_agent": None})
    print(f"[售后入口] active_agent={result2.get('active_agent')}")
    print(f"[售后入口] 回答: {result2['messages'][-1].content}")

    result3 = graph.invoke({"messages": [{"role": "user", "content": "你们的课程有效期是多久？买了不满意能退钱吗"}], "active_agent": None})
    transferred = [c["name"] for m in result3["messages"] if getattr(m, "tool_calls", None) for c in m.tool_calls]
    print(f"[交接] 售前调用的工具={transferred}")
    print(f"[交接] active_agent={result3.get('active_agent')}")
    print(f"[交接] 回答: {result3['messages'][-1].content}")


if __name__ == "__main__":
    part1_agent_as_tool()
    part2_graph_handoff()
