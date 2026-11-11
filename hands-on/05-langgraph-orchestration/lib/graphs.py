"""图构建：主案例 + 逐日子图 + 导出辅助。

主图结构（一条链串起四天课次）：
    START → load_profile
              ├→ plan_attractions ┐
              └→ plan_food ───────┴→ merge_cost → daily_detail(子图) → review_budget
    review_budget ──达标──→ await_approval → save_profile → finalize → END
                  └─超支──→ revise_plan → review_budget
"""
from pathlib import Path
from typing import Annotated, TypedDict

import operator

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from .llm import llm
from .nodes import (
    await_approval,
    finalize,
    load_profile,
    make_save_profile,
    merge_cost,
    plan_attractions,
    plan_food,
    review_budget,
    revise_plan,
    route_budget,
)
from .state import TravelRequest, TravelState, UserContext


class DayState(TypedDict, total=False):
    """子图状态：只声明父图同名 key 的子集，挂载后可直接读写。"""

    request: TravelRequest
    attractions: str
    level: str
    daily_plans: Annotated[list[str], operator.add]


def detail_days(state: DayState) -> dict:
    """子图唯一节点：把已排好的景点拆成逐日细则。"""
    req = state["request"]
    level = state.get("level", "standard")
    prompt = (
        f"为{req['city']}{req['days']}天行程写逐日安排，档位：{level}。\n"
        f"已有景点安排：{state.get('attractions', '')}\n"
        "每天 2-3 个活动，标出大致时间段，不要重复景点，控制在 200 字以内。"
    )
    text = llm(max_tokens=420).invoke(
        [SystemMessage(content="你是旅行规划师，只输出逐日安排。"), HumanMessage(content=prompt)]
    ).content
    return {"daily_plans": [text.strip()]}


def build_daily_subgraph():
    """逐日细化子图：单独编译，既能被父图挂载，也能独立 invoke。"""
    builder = StateGraph(DayState)
    builder.add_node("detail_days", detail_days)
    builder.add_edge(START, "detail_days")
    builder.add_edge("detail_days", END)
    return builder.compile()


def build_concierge_graph(checkpointer=None, store=None):
    """主图：并行规划 → 预算评估 → 人工审批 → 长期记忆沉淀。"""
    builder = StateGraph(TravelState, context_schema=UserContext)

    builder.add_node("load_profile", load_profile)
    builder.add_node("plan_attractions", plan_attractions)
    builder.add_node("plan_food", plan_food)
    builder.add_node("merge_cost", merge_cost)
    builder.add_node("daily_detail", build_daily_subgraph())
    builder.add_node("review_budget", review_budget)
    builder.add_node("revise_plan", revise_plan)
    builder.add_node("await_approval", await_approval)
    builder.add_node("save_profile", make_save_profile())
    builder.add_node("finalize", finalize)

    builder.add_edge(START, "load_profile")
    # 两条出边 = 并行 fan-out，两条入边 = 汇聚等齐
    builder.add_edge("load_profile", "plan_attractions")
    builder.add_edge("load_profile", "plan_food")
    builder.add_edge("plan_attractions", "merge_cost")
    builder.add_edge("plan_food", "merge_cost")
    builder.add_edge("merge_cost", "daily_detail")
    builder.add_edge("daily_detail", "review_budget")
    builder.add_conditional_edges(
        "review_budget", route_budget, ["await_approval", "revise_plan"]
    )
    builder.add_edge("revise_plan", "review_budget")
    builder.add_edge("await_approval", "save_profile")
    builder.add_edge("save_profile", "finalize")
    builder.add_edge("finalize", END)

    return builder.compile(checkpointer=checkpointer, store=store)


def draw(graph, out_path: str | Path) -> str:
    """导出图结构：优先 PNG，失败时退化为 Mermaid 文本。

    draw_mermaid_png 依赖网络（mermaid.ink），离线环境会失败；
    文本版在任何环境都能生成，方便进仓库做结构证据。
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    graph_repr = graph.get_graph(xray=True)
    try:
        out_path.write_bytes(graph_repr.draw_mermaid_png())
        return f"PNG {out_path.name}"
    except Exception:
        mmd = out_path.with_suffix(".mmd")
        mmd.write_text(graph_repr.draw_mermaid(), encoding="utf-8")
        return f"Mermaid {mmd.name}"
