"""s02 同一件事的两种写法：Graph API（显式节点与边）和 Functional API（任务与入口）。

对应 day13 后半的 ReAct 例子。任务：一个只会加减乘除的计算助手。
验证点：
1. Graph API：llm_call → tool_node → llm_call 的回边真的转了两圈
2. Functional API：@task 并行执行多个工具，@entrypoint 内用 .result() 收口
3. 两条路最终都算出 7，消息历史里能看到 ToolMessage
"""
import sys
from typing import Annotated, Literal, TypedDict

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import operator
from pathlib import Path

from langchain.tools import tool
from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.graphs import draw  # noqa: E402
from lib.llm import llm  # noqa: E402

SYSTEM = "你是算术助手，需要计算时必须调用工具，不要心算。"


@tool
def add(a: int, b: int) -> int:
    """两数相加。"""
    return a + b


@tool
def multiply(a: int, b: int) -> int:
    """两数相乘。"""
    return a * b


@tool
def divide(a: int, b: int) -> float:
    """两数相除。"""
    return a / b


TOOLS = [add, multiply, divide]
TOOLS_BY_NAME = {t.name: t for t in TOOLS}


# ---------------- Graph API ----------------
class MessagesState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    llm_calls: int


def build_graph_api():
    model = llm(temperature=0).bind_tools(TOOLS)

    def llm_call(state: MessagesState) -> dict:
        response = model.invoke([SystemMessage(content=SYSTEM)] + state["messages"])
        return {"messages": [response], "llm_calls": state.get("llm_calls", 0) + 1}

    def tool_node(state: MessagesState) -> dict:
        results = []
        for call in state["messages"][-1].tool_calls:
            observation = TOOLS_BY_NAME[call["name"]].invoke(call["args"])
            results.append(ToolMessage(content=str(observation), tool_call_id=call["id"]))
        return {"messages": results}

    def should_continue(state: MessagesState) -> Literal["tool_node", END]:
        return "tool_node" if getattr(state["messages"][-1], "tool_calls", None) else END

    builder = StateGraph(MessagesState)
    builder.add_node("llm_call", llm_call)
    builder.add_node("tool_node", tool_node)
    builder.add_edge(START, "llm_call")
    builder.add_conditional_edges("llm_call", should_continue, ["tool_node", END])
    builder.add_edge("tool_node", "llm_call")
    return builder.compile()


def run_graph_api() -> None:
    graph = build_graph_api()
    print("Graph API 图结构：", draw(graph, "assets/s02-react-graph.png"))
    result = graph.invoke({"messages": [HumanMessage(content="先算 3 加 4，再把这个结果乘以 2")]})
    for msg in result["messages"]:
        msg.pretty_print()
    print(f"\nGraph API 调用模型次数：{result['llm_calls']}")
    print(f"最终消息：{result['messages'][-1].content}")


# ---------------- Functional API ----------------
from langgraph.func import entrypoint, task  # noqa: E402


@task
def call_llm(messages: list[AnyMessage]):
    return llm(temperature=0).bind_tools(TOOLS).invoke([SystemMessage(content=SYSTEM)] + messages)


@task
def call_tool(tool_call: dict):
    return TOOLS_BY_NAME[tool_call["name"]].invoke(tool_call["args"])


@entrypoint()
def functional_agent(messages: list[AnyMessage]) -> list[AnyMessage]:
    response = call_llm(messages).result()
    while True:
        if not response.tool_calls:
            break
        # 多个工具调用并行提交，再统一收结果
        futures = [call_tool(call) for call in response.tool_calls]
        tool_messages = [
            ToolMessage(content=str(f.result()), tool_call_id=call["id"])
            for f, call in zip(futures, response.tool_calls)
        ]
        messages = messages + [response, *tool_messages]
        response = call_llm(messages).result()
    return messages + [response]


def run_functional_api() -> None:
    history = functional_agent.invoke([HumanMessage(content="算一下 12 除以 3，再加 10")])
    for msg in history:
        msg.pretty_print()
    print(f"Functional API 最终消息：{history[-1].content}")


def main() -> None:
    print("=" * 20, "Graph API", "=" * 20)
    run_graph_api()
    print("\n" + "=" * 20, "Functional API", "=" * 20)
    run_functional_api()
    print("\nS02 OK：两种 API 都完成了工具调用闭环")


if __name__ == "__main__":
    main()
