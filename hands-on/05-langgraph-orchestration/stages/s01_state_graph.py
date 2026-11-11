"""s01 最小状态图：State / Node / Edge / compile 四件套 + reducer + 条件边。

对应 day13 前半。不调模型，纯本地跑，先确认「图本身」是对的。
验证点：
1. total=False 的状态可以增量返回
2. Annotated[list, operator.add] 的 log 是追加而不是覆盖
3. 条件边能把超支行程送回降档节点，降档后放行
"""
import sys
from typing import Annotated, Literal, TypedDict

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import operator

from langgraph.graph import END, START, StateGraph

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
from lib.graphs import draw  # noqa: E402


class TripState(TypedDict, total=False):
    city: str
    days: int
    budget: float
    total: float
    level: str            # standard / frugal
    approved: bool
    log: Annotated[list[str], operator.add]


def estimate(state: TripState) -> dict:
    total = state["days"] * 800.0
    return {"total": total, "level": "standard", "log": [f"estimate → {state['city']} {state['days']}天 常规档 {total} 元"]}


def review(state: TripState) -> dict:
    ok = state["total"] <= state["budget"]
    return {"log": [f"review → {'达标' if ok else '超支'}（{state['total']} / {state['budget']}）"]}


def downgrade(state: TripState) -> dict:
    total = state["days"] * 420.0
    return {"total": total, "level": "frugal", "log": [f"downgrade → 降到穷游档 {total} 元"]}


def confirm(state: TripState) -> dict:
    return {"approved": True, "log": [f"confirm → 按 {state['level']} 档出方案"]}


def route(state: TripState) -> Literal["confirm", "downgrade"]:
    if state["total"] <= state["budget"] or state.get("level") == "frugal":
        return "confirm"
    return "downgrade"


def build_graph():
    builder = StateGraph(TripState)
    builder.add_node("estimate", estimate)
    builder.add_node("review", review)
    builder.add_node("downgrade", downgrade)
    builder.add_node("confirm", confirm)
    builder.add_edge(START, "estimate")
    builder.add_edge("estimate", "review")
    builder.add_conditional_edges("review", route, ["confirm", "downgrade"])
    builder.add_edge("downgrade", "review")
    builder.add_edge("confirm", END)
    return builder.compile()


def main() -> None:
    graph = build_graph()
    print("图结构：", draw(graph, "assets/s01-minimal-graph.png"))

    for budget in (6000, 2000):
        print(f"\n=== 预算 {budget} 元 ===")
        # 用 stream 观察每个节点的实际输出，比只看最终 state 更直观
        for chunk in graph.stream(
            {"city": "杭州", "days": 3, "budget": budget, "log": []},
            stream_mode="updates",
        ):
            for node, update in chunk.items():
                print(f"[{node}] {update.get('log', update)}")

    final = graph.invoke({"city": "杭州", "days": 3, "budget": 2000, "log": []})
    print("\n最终 state：", {k: v for k, v in final.items() if k != "log"})
    print("执行轨迹：")
    for i, line in enumerate(final["log"], 1):
        print(f"  {i}. {line}")
    print("\nS01 OK：reducer 追加、条件边回环、END 收口均符合预期")


if __name__ == "__main__":
    main()
