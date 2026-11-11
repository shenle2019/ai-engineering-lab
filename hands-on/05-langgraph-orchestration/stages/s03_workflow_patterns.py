"""s03 七种工作流模式：同样的模型能力，不同的控制流。

对应 day14 前半。每个模式都是一个最小可跑图，重点看「谁能决定下一步」：
- 代码决定：提示链、并行化、路由
- 模型决定：编排者-工作者、评估者-优化器、Agent

为控制调用成本，所有提示词都压到 60 字以内、max_tokens=120。
"""
import sys
from typing import Annotated, Literal, TypedDict

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import operator
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.graphs import draw  # noqa: E402
from lib.llm import llm, structured  # noqa: E402
from lib.state import Section, Sections, TopicChoice, Verdict  # noqa: E402

CALLS = {"count": 0}


def ask(prompt: str, max_tokens: int = 120) -> str:
    CALLS["count"] += 1
    return llm(max_tokens=max_tokens, temperature=0.5).invoke(prompt).content.strip()


# ---------- 1. LLM 增强：单节点 + 结构化输出 ----------
def demo_llm_boost() -> None:
    print("\n[1] LLM 增强（with_structured_output）")
    judge = structured(Verdict)
    verdict = judge.invoke("判断这份行程文案是否可以直接交付：杭州三日游，西湖骑行加龙井问茶。")
    CALLS["count"] += 1
    print(f"    passed={verdict.passed} feedback={verdict.feedback}")


# ---------- 2. 提示链：固定流水线 + 代码裁决的 gate ----------
class ChainState(TypedDict, total=False):
    topic: str
    draft: str
    final: str


def chain_graph():
    def write(state: ChainState) -> dict:
        return {"draft": ask(f"写一句{state['topic']}的旅行宣传语，不超过 20 字")}

    def gate(state: ChainState) -> str:
        # 代码决定是否继续：没有感叹号就再润色一轮
        return "polish" if "！" not in state["draft"] else END

    def polish(state: ChainState) -> dict:
        return {"final": ask(f"给这句宣传语加一个感叹号式的收尾：{state['draft']}")}

    builder = StateGraph(ChainState)
    builder.add_node("write", write)
    builder.add_node("polish", polish)
    builder.add_edge(START, "write")
    builder.add_conditional_edges("write", gate, ["polish", END])
    builder.add_edge("polish", END)
    return builder.compile()


# ---------- 3. 并行化：两个分支同时跑，汇聚后拼接 ----------
class ParallelState(TypedDict, total=False):
    city: str
    highlight: str
    food: str
    summary: str


def parallel_graph():
    def highlight(state: ParallelState) -> dict:
        return {"highlight": ask(f"用一句话推荐{state['city']}最值得去的一个地方")}

    def food(state: ParallelState) -> dict:
        return {"food": ask(f"用一句话推荐{state['city']}必吃的一道菜")}

    def merge(state: ParallelState) -> dict:
        return {"summary": f"{state['highlight']} / {state['food']}"}

    builder = StateGraph(ParallelState)
    builder.add_node("highlight", highlight)
    builder.add_node("food", food)
    builder.add_node("merge", merge)
    builder.add_edge(START, "highlight")
    builder.add_edge(START, "food")
    builder.add_edge("highlight", "merge")
    builder.add_edge("food", "merge")
    builder.add_edge("merge", END)
    return builder.compile()


# ---------- 4. 路由：模型选路，代码执行 ----------
class RouteState(TypedDict, total=False):
    question: str
    route: str
    answer: str


def router_graph():
    classifier = structured(TopicChoice)

    def classify(state: RouteState) -> dict:
        CALLS["count"] += 1
        return {"route": classifier.invoke(state["question"]).topic}

    def history(state: RouteState) -> dict:
        return {"answer": ask(f"用一句话回答历史问题：{state['question']}")}

    def food(state: RouteState) -> dict:
        return {"answer": ask(f"用一句话回答美食问题：{state['question']}")}

    def nature(state: RouteState) -> dict:
        return {"answer": ask(f"用一句话回答自然风光问题：{state['question']}")}

    builder = StateGraph(RouteState)
    builder.add_node("classify", classify)
    builder.add_node("history", history)
    builder.add_node("food", food)
    builder.add_node("nature", nature)
    builder.add_edge(START, "classify")
    builder.add_conditional_edges(
        "classify", lambda s: s["route"], {"history": "history", "food": "food", "nature": "nature"}
    )
    for node in ("history", "food", "nature"):
        builder.add_edge(node, END)
    return builder.compile()


# ---------- 5. 编排者-工作者：Send 动态扇出 ----------
class ReportState(TypedDict, total=False):
    topic: str
    sections: list[Section]
    section: Section
    finished: Annotated[list[str], operator.add]
    report: str


def orchestrator_graph():
    planner = structured(Sections)

    def plan(state: ReportState) -> dict:
        CALLS["count"] += 1
        outline = planner.invoke(
            [SystemMessage(content="给出 2 个章节即可，越短越好。"), HumanMessage(content=f"主题：{state['topic']}")]
        )
        return {"sections": outline.sections}

    def worker(state: ReportState) -> dict:
        sec = state["section"]
        return {"finished": [f"{sec.name}：{ask(f'用 30 字写{sec.name}，要点：{sec.description}', 90)}"]}

    def synthesize(state: ReportState) -> dict:
        return {"report": "\n".join(state["finished"])}

    def fan_out(state: ReportState) -> list[Send]:
        return [Send("worker", {"section": s}) for s in state["sections"]]

    builder = StateGraph(ReportState)
    builder.add_node("plan", plan)
    builder.add_node("worker", worker)
    builder.add_node("synthesize", synthesize)
    builder.add_edge(START, "plan")
    builder.add_conditional_edges("plan", fan_out, ["worker"])
    builder.add_edge("worker", "synthesize")
    builder.add_edge("synthesize", END)
    return builder.compile()


# ---------- 6. 评估者-优化器：回边 + 上限 ----------
class LoopState(TypedDict, total=False):
    draft: str
    feedback: str
    attempts: int


def evaluator_graph():
    judge = structured(Verdict)

    def generate(state: LoopState) -> dict:
        base = state.get("draft") or ""
        hint = state.get("feedback") or ""
        return {"draft": ask(f"写一句杭州旅行 slogan。{('在上一版基础上改进：' + base + '；意见：' + hint) if base else ''}")}

    def evaluate(state: LoopState) -> dict:
        CALLS["count"] += 1
        v = judge.invoke(f"这句 slogan 够好吗：{state['draft']}")
        return {"feedback": v.feedback, "attempts": state.get("attempts", 0) + 1}

    def route(state: LoopState) -> str:
        return "generate" if state.get("attempts", 0) < 2 and state.get("feedback") else END

    builder = StateGraph(LoopState)
    builder.add_node("generate", generate)
    builder.add_node("evaluate", evaluate)
    builder.add_edge(START, "generate")
    builder.add_edge("generate", "evaluate")
    builder.add_conditional_edges("evaluate", route, ["generate", END])
    return builder.compile()


def main() -> None:
    demo_llm_boost()

    print("\n[2] 提示链（gate 由代码裁决）")
    chain = chain_graph()
    print("    ", draw(chain, "assets/s03-prompt-chain.png"))
    out = chain.invoke({"topic": "杭州西湖"})
    print(f"    draft={out['draft']} | final={out.get('final', '（已达标未润色）')}")

    print("\n[3] 并行化（两个分支同一超步）")
    par = parallel_graph()
    out = par.invoke({"city": "成都"})
    print(f"    {out['summary']}")

    print("\n[4] 路由（模型只选路，代码执行）")
    for q in ("兵马俑是哪个朝代的", "成都有什么好吃的"):
        out = router_graph().invoke({"question": q})
        print(f"    {q} → 路由={out['route']} 答案={out['answer']}")

    print("\n[5] 编排者-工作者（Send 扇出）")
    orch = orchestrator_graph()
    print("    ", draw(orch, "assets/s03-orchestrator.png"))
    out = orch.invoke({"topic": "杭州两日游"})
    print(f"    大纲 {len(out['sections'])} 章，汇总：\n{out['report']}")

    print("\n[6] 评估者-优化器（最多两轮）")
    out = evaluator_graph().invoke({})
    print(f"    attempts={out['attempts']} draft={out['draft']}")

    print(f"\nS03 OK：六种模式全部跑通，模型调用合计 {CALLS['count']} 次（Agent 模式见 s02）")


if __name__ == "__main__":
    main()
