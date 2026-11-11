"""s09 持久执行：进程崩了，检查点还在，续跑不重复干活。

对应 day16 后半。验证点：
1. 节点抛异常后，已完成节点的检查点保留
2. 重启后 invoke(None, config) 只跑没完成的节点（计数器证明 prepare 只执行一次）
3. 用状态标记位实现「精确一次」的副作用（通知只发一次）
"""
import sys
import sqlite3
import tempfile
from pathlib import Path
from typing import Annotated, TypedDict

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import operator

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.graphs import draw  # noqa: E402


class PoemState(TypedDict, total=False):
    topic: str
    poem: str
    status: str
    notified: bool
    retry: int                       # >0 时故意再跑一次 notify，用来验证幂等
    log: Annotated[list[str], operator.add]


FAIL = {"enabled": True}
EXEC = {"prepare": 0, "write": 0, "notify": 0}


def prepare(state: PoemState) -> dict:
    EXEC["prepare"] += 1
    return {"topic": "春日西湖", "status": "prepared", "log": ["prepare：已确定主题"]}


def write_poem(state: PoemState) -> dict:
    EXEC["write"] += 1
    if FAIL["enabled"]:
        raise RuntimeError("模拟模型服务中断（第一次运行必然失败）")
    return {"poem": "水光潋滟晴方好，山色空蒙雨亦奇。", "status": "written", "log": ["write_poem：诗已生成"]}


def notify(state: PoemState) -> dict:
    EXEC["notify"] += 1
    # 幂等：靠状态里的标记位，重复执行也只发一次
    if state.get("notified"):
        return {"retry": state.get("retry", 0) - 1, "log": ["notify：已通知过，跳过"]}
    return {
        "notified": True,
        "retry": state.get("retry", 0) - 1,
        "log": ["notify：已发送通知（仅一次）"],
    }


def after_notify(state: PoemState) -> str:
    # retry 表示「还能再重试几次」：每进一次 notify 减 1，减到负数才收工
    return "notify" if state.get("retry", 0) >= 0 else END


def build_graph(saver):
    builder = StateGraph(PoemState)
    builder.add_node("prepare", prepare)
    builder.add_node("write_poem", write_poem)
    builder.add_node("notify", notify)
    builder.add_edge(START, "prepare")
    builder.add_edge("prepare", "write_poem")
    builder.add_edge("write_poem", "notify")
    builder.add_conditional_edges("notify", after_notify, ["notify", END])
    return builder.compile(checkpointer=saver)


def main() -> None:
    db = Path(tempfile.gettempdir()) / "lg_s09_durable.db"
    db.unlink(missing_ok=True)
    conn = sqlite3.connect(db, check_same_thread=False)
    saver = SqliteSaver(conn)
    graph = build_graph(saver)
    print("图结构：", draw(graph, "assets/s09-durable.png"))

    config = {"configurable": {"thread_id": "poem-1"}}

    print("\n[1] 第一次运行：write_poem 抛异常")
    try:
        graph.invoke({"status": "init"}, config)
    except RuntimeError as exc:
        print(f"    按预期失败：{exc}")
    print(f"    失败后执行计数：{EXEC}")

    state = graph.get_state(config)
    print(f"    检查点停在 next={state.next}，已完成状态 status={state.values.get('status')}")

    print("\n[2] 模拟服务重启：换一个进程内对象，但用同一个 SQLite 文件")
    FAIL["enabled"] = False
    new_conn = sqlite3.connect(db, check_same_thread=False)
    new_graph = build_graph(SqliteSaver(new_conn))
    result = new_graph.invoke(None, config)
    print(f"    续跑结果：{result['poem']}")
    print(f"    总执行计数：{EXEC}（prepare 仍为 1，write 为 2：失败 1 次 + 成功 1 次）")

    print("\n[3] 精确一次：让 notify 被重试一次，第二次变成空操作")
    before = EXEC["notify"]
    cfg2 = {"configurable": {"thread_id": "poem-2"}}
    new_graph.invoke({"status": "init", "retry": 1}, cfg2)
    print(f"    notify 实际执行 {EXEC['notify'] - before} 次，只发了一次通知")
    print(f"    notified={new_graph.get_state(cfg2).values['notified']}")
    print("    轨迹：")
    for i, line in enumerate(new_graph.get_state(cfg2).values["log"], 1):
        print(f"      {i}. {line}")

    new_conn.close()
    conn.close()
    db.unlink(missing_ok=True)
    print("\nS09 OK：崩溃恢复只补未完成节点，副作用靠状态标记做幂等")


if __name__ == "__main__":
    main()
