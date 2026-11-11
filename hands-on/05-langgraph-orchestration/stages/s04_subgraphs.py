"""s04 子图：两种挂法 + 持久化继承 + 子图流式。

对应 day14 后半。子图的价值是把一块流程封装成可复用单元，关键是搞清两件事：
1. 状态怎么传：节点内 invoke（手动转换） vs add_node（共享同名 key）
2. 持久化怎么算：父图带 checkpointer 时子图默认继承；compile(checkpointer=True) 才独立
"""
import sys
import tempfile
from pathlib import Path
from typing import Annotated, TypedDict

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import operator
import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.graphs import draw  # noqa: E402


class SharedState(TypedDict, total=False):
    text: str
    processed: str
    log: Annotated[list[str], operator.add]


# ---------------- 子图定义 ----------------
def _sub_nodes():
    def normalize(state: SharedState) -> dict:
        return {"text": state["text"].strip().lower(), "log": ["子图.normalize"]}

    def decorate(state: SharedState) -> dict:
        return {"processed": f"<<{state['text']}>>", "log": ["子图.decorate"]}

    return normalize, decorate


def build_subgraph(checkpointer=None):
    normalize, decorate = _sub_nodes()
    builder = StateGraph(SharedState)
    builder.add_node("normalize", normalize)
    builder.add_node("decorate", decorate)
    builder.add_edge(START, "normalize")
    builder.add_edge("normalize", "decorate")
    builder.add_edge("decorate", END)
    return builder.compile(checkpointer=checkpointer)


# ---------------- 写法 A：在节点里手动调用 ----------------
def build_parent_via_call(subgraph):
    def call_sub(state: SharedState) -> dict:
        # 只有子图需要的字段传进去，结果再手动搬回父状态
        out = subgraph.invoke({"text": state["text"], "log": []})
        return {"processed": out["processed"], "log": ["父图.call_sub"] + out["log"]}

    builder = StateGraph(SharedState)
    builder.add_node("call_sub", call_sub)
    builder.add_edge(START, "call_sub")
    builder.add_edge("call_sub", END)
    return builder.compile()


# ---------------- 写法 B：直接把子图当节点 ----------------
def build_parent_via_node(subgraph):
    def preclean(state: SharedState) -> dict:
        return {"text": state["text"], "log": ["父图.preclean"]}

    builder = StateGraph(SharedState)
    builder.add_node("preclean", preclean)
    builder.add_node("subgraph", subgraph)   # 共享 state，一行挂载
    builder.add_edge(START, "preclean")
    builder.add_edge("preclean", "subgraph")
    builder.add_edge("subgraph", END)
    return builder.compile()


def main() -> None:
    payload = {"text": "  LangGraph SUBGRAPH  ", "log": []}

    print("[A] 节点内 invoke")
    parent_a = build_parent_via_call(build_subgraph())
    out_a = parent_a.invoke(dict(payload))
    print("    processed =", out_a["processed"])
    print("    log =", out_a["log"])

    print("\n[B] add_node 挂载（共享 state）")
    parent_b = build_parent_via_node(build_subgraph())
    print("    ", draw(parent_b, "assets/s04-parent-with-subgraph.png"))
    out_b = parent_b.invoke(dict(payload))
    print("    processed =", out_b["processed"])
    print("    log =", out_b["log"])
    print("    注：preclean 出现两次是共享状态的副作用——子图输入继承了父图已累积的 log，")
    print("        子图结束时又把整份 log 作为输出写回，reducer 再追加一次。")
    print("        避开方式：子图用不同名的私有 key，或子图只返回本段新增的内容。")

    print("\n[C] 持久化：父图带 checkpointer，子图自动继承同一个 thread")
    db = Path(tempfile.gettempdir()) / "lg_s04_subgraph.db"
    db.unlink(missing_ok=True)
    conn = sqlite3.connect(db, check_same_thread=False)
    saver = SqliteSaver(conn)
    sub = build_subgraph()
    # 父图编译时带 saver；子图自身没传 checkpointer，会继承父图的
    builder = StateGraph(SharedState)
    builder.add_node("preclean", lambda s: {"text": s["text"], "log": ["父图.preclean"]})
    builder.add_node("subgraph", sub)
    builder.add_edge(START, "preclean")
    builder.add_edge("preclean", "subgraph")
    builder.add_edge("subgraph", END)
    parent_c = builder.compile(checkpointer=saver)

    config = {"configurable": {"thread_id": "s04-thread-1"}}
    parent_c.invoke({"text": "  继承 THREAD  ", "log": []}, config)
    parent_state = parent_c.get_state(config)
    print("    父图 processed =", parent_state.values["processed"])
    print("    父图轨迹 =", parent_state.values["log"])
    # 落到同一个 sqlite 里的检查点会按命名空间区分：父图为空串，子图是 "subgraph:<任务id>"
    rows = conn.execute(
        "SELECT DISTINCT checkpoint_ns FROM checkpoints WHERE thread_id = ?", ("s04-thread-1",)
    ).fetchall()
    child_ns = sorted({ns for (ns,) in rows if ns})
    print(f"    检查点命名空间：父图 ''，子图 {child_ns}")

    print("\n[D] 子图流式：subgraphs=True 能看到子图内部节点")
    for namespace, chunk in parent_b.stream(dict(payload), stream_mode="updates", subgraphs=True):
        node = next(iter(chunk))
        scope = "子图" if namespace else "父图"
        print(f"    {scope} node={node} namespace={namespace}")

    conn.close()
    db.unlink(missing_ok=True)
    print("\nS04 OK：两种挂法、持久化继承、子图流式均可观察")


if __name__ == "__main__":
    main()
