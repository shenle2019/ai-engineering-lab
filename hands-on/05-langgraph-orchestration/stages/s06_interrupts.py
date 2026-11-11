"""s06 中断：把人放进流程里。

对应 day15 后半。四种典型人机协同：
1. 批准/拒绝：resume 传 bool
2. 审查/编辑：resume 传 dict，节点据此改写状态
3. 工具内中断：中断点在工具函数里，恢复后整个节点从头重跑
4. 非法输入重试：校验不过就再次 interrupt

关键前提：interrupt 必须有 checkpointer + thread_id，否则无处暂停。
"""
import sys
from pathlib import Path
from typing import Literal, Optional, TypedDict

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from langchain.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.graphs import draw  # noqa: E402


def demo_approve() -> None:
    print("[1] 批准 / 拒绝")

    class State(TypedDict, total=False):
        action: str
        status: str

    def approval(state: State) -> Command[Literal["proceed", "cancel"]]:
        decision = interrupt({"question": "是否执行这笔转账？", "details": state["action"]})
        return Command(goto="proceed" if decision else "cancel")

    def proceed(state: State) -> dict:
        return {"status": "approved：已转账"}

    def cancel(state: State) -> dict:
        return {"status": "rejected：已取消"}

    builder = StateGraph(State)
    builder.add_node("approval", approval)
    builder.add_node("proceed", proceed)
    builder.add_node("cancel", cancel)
    builder.add_edge(START, "approval")
    builder.add_edge("proceed", END)
    builder.add_edge("cancel", END)
    graph = builder.compile(checkpointer=InMemorySaver())

    config = {"configurable": {"thread_id": "approve-1"}}
    paused = graph.invoke({"action": "转账 500 元"}, config)
    print(f"    暂停时 __interrupt__ = {paused['__interrupt__'][0].value}")

    resumed = graph.invoke(Command(resume=True), config)
    print(f"    恢复后 status = {resumed['status']}")

    # 再走一条拒绝路径，确认两个分支都能到达
    config2 = {"configurable": {"thread_id": "approve-2"}}
    graph.invoke({"action": "转账 900 元"}, config2)
    print(f"    拒绝后 status = {graph.invoke(Command(resume=False), config2)['status']}")


def demo_edit_state() -> None:
    print("\n[2] 审查 / 编辑：resume 传 dict 改状态")

    class State(TypedDict, total=False):
        draft: str
        final: str

    def review(state: State) -> dict:
        edited = interrupt({"question": "请审阅并可直接改写", "draft": state["draft"]})
        new_text = edited.get("draft", state["draft"]) if isinstance(edited, dict) else state["draft"]
        return {"draft": new_text}

    def publish(state: State) -> dict:
        return {"final": f"已发布：{state['draft']}"}

    builder = StateGraph(State)
    builder.add_node("review", review)
    builder.add_node("publish", publish)
    builder.add_edge(START, "review")
    builder.add_edge("review", "publish")
    builder.add_edge("publish", END)
    graph = builder.compile(checkpointer=InMemorySaver())

    config = {"configurable": {"thread_id": "edit-1"}}
    graph.invoke({"draft": "杭州三日游，随便逛逛。"}, config)
    out = graph.invoke(Command(resume={"draft": "杭州三日游：西湖骑行 → 灵隐寺 → 龙井问茶。"}), config)
    print(f"    {out['final']}")


def demo_tool_interrupt() -> None:
    print("\n[3] 工具内中断：恢复后节点从头重跑")

    class State(TypedDict, total=False):
        city: str
        booking: str

    @tool
    def book_hotel(city: str) -> str:
        """预订酒店，需要人工确认房型。"""
        choice = interrupt({"question": f"{city} 订哪种房型？", "options": ["大床", "双床"]})
        return f"{city} 已订{choice}房"

    def call_tool(state: State) -> dict:
        return {"booking": book_hotel.invoke({"city": state["city"]})}

    builder = StateGraph(State)
    builder.add_node("call_tool", call_tool)
    builder.add_edge(START, "call_tool")
    builder.add_edge("call_tool", END)
    graph = builder.compile(checkpointer=InMemorySaver())

    config = {"configurable": {"thread_id": "tool-1"}}
    paused = graph.invoke({"city": "杭州"}, config)
    print(f"    工具内暂停：{paused['__interrupt__'][0].value}")
    out = graph.invoke(Command(resume="大床"), config)
    print(f"    恢复后 booking = {out['booking']}")


def demo_validate_input() -> None:
    print("\n[4] 验证人工输入：非法值再次中断")

    class State(TypedDict, total=False):
        age: int
        attempts: int

    def ask_age(state: State) -> dict:
        attempts = state.get("attempts", 0)
        while True:
            attempts += 1
            value = interrupt({"question": "请输入 1-120 的年龄", "attempt": attempts})
            try:
                age = int(value)
            except (TypeError, ValueError):
                continue
            if 1 <= age <= 120:
                return {"age": age, "attempts": attempts}

    builder = StateGraph(State)
    builder.add_node("ask_age", ask_age)
    builder.add_edge(START, "ask_age")
    builder.add_edge("ask_age", END)
    graph = builder.compile(checkpointer=InMemorySaver())

    config = {"configurable": {"thread_id": "validate-1"}}
    graph.invoke({}, config)
    graph.invoke(Command(resume="不是数字"), config)
    out = graph.invoke(Command(resume=28), config)
    print(f"    最终 age={out['age']}，本次节点执行里 interrupt 被调用 {out['attempts']} 次")
    print("    注：节点每次恢复都从头重跑，上一轮的局部变量不会保留；上一轮的非法输入")
    print("        会在重跑时被第一个 interrupt 重新拿到，所以计数从 1 重新开始。")
    print("        需要跨轮累计的计数必须写进状态，不能放在局部变量里。")

    print("\n    ", draw(graph, "assets/s06-interrupt-validate.png"))


def main() -> None:
    demo_approve()
    demo_edit_state()
    demo_tool_interrupt()
    demo_validate_input()
    print("\nS06 OK：四种中断形态都能暂停并恢复")


if __name__ == "__main__":
    main()
