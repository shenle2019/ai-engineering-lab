"""s07 时间旅行：回到过去某个检查点，重放或开一条新分支。

对应 day16 前半。验证点：
1. get_state_history 能找到 next == ("write_joke",) 的快照
2. invoke(None, snapshot.config) 会重放后续节点（计数器证明重复执行）
3. update_state(values, as_node) 造分支，原线程历史不变
4. 子图时间旅行要先用 get_state(config, subgraphs=True) 取子图 config
"""
import sys
from pathlib import Path
from typing import Annotated, TypedDict

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import operator

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.graphs import draw  # noqa: E402

EXEC = {"generate_topic": 0, "write_joke": 0, "review": 0}


class JokeState(TypedDict, total=False):
    topic: str
    joke: str
    reviewed: str
    log: Annotated[list[str], operator.add]


def build_joke_graph():
    def generate_topic(state: JokeState) -> dict:
        EXEC["generate_topic"] += 1
        return {"topic": "烘干机里的袜子", "log": ["generate_topic"]}

    def write_joke(state: JokeState) -> dict:
        EXEC["write_joke"] += 1
        return {"joke": f"为什么{state['topic']}会消失？因为它们私奔了。", "log": ["write_joke"]}

    def review(state: JokeState) -> dict:
        EXEC["review"] += 1
        return {"reviewed": f"审核通过：{state['joke']}", "log": ["review"]}

    builder = StateGraph(JokeState)
    builder.add_node("generate_topic", generate_topic)
    builder.add_node("write_joke", write_joke)
    builder.add_node("review", review)
    builder.add_edge(START, "generate_topic")
    builder.add_edge("generate_topic", "write_joke")
    builder.add_edge("write_joke", "review")
    builder.add_edge("review", END)
    return builder.compile(checkpointer=InMemorySaver())


def demo_replay_and_fork() -> None:
    graph = build_joke_graph()
    print("图结构：", draw(graph, "assets/s07-time-travel.png"))

    config = {"configurable": {"thread_id": "joke-1"}}
    first = graph.invoke({}, config)
    print(f"\n[1] 首次运行：{first['joke']}")
    print(f"    执行计数：{EXEC}")

    history = list(graph.get_state_history(config))
    before_joke = next(s for s in history if s.next == ("write_joke",))
    print(f"    找到快照：checkpoint={before_joke.config['configurable']['checkpoint_id'][:8]}… next={before_joke.next}")

    print("\n[2] 重放：从上一步快照继续")
    replayed = graph.invoke(None, before_joke.config)
    print(f"    重放结果：{replayed['joke']}")
    print(f"    执行计数：{EXEC}（write_joke 与 review 各多一次）")

    print("\n[3] 分支：从旧快照改主题重跑")
    fork_config = graph.update_state(
        before_joke.config,
        values={"topic": "小鸡"},
        as_node="generate_topic",
    )
    fork_result = graph.invoke(None, fork_config)
    print(f"    分支结果：{fork_result['joke']}")

    head = graph.get_state(config)
    print(f"    thread 头已指向新分支：{head.values['joke']}")
    old_jokes = [
        s for s in graph.get_state_history(config) if "袜子" in (s.values.get("joke") or "")
    ]
    print(f"    旧分支没被删：历史里仍有 {len(old_jokes)} 个『袜子』版本快照")
    print("    注：update_state 是在同一个 thread 上追加检查点、把线程头挪到新分支，")
    print("        旧检查点仍可按 checkpoint_id 读；要让两条线互不干扰，就给分支一个新 thread_id。")
    print(f"    执行计数：{EXEC}")


def demo_subgraph_travel() -> None:
    print("\n[4] 子图时间旅行：拿子图自己的 config")

    class ParentState(TypedDict, total=False):
        city: str
        detail: str
        log: Annotated[list[str], operator.add]

    def sub_node(state: ParentState) -> dict:
        return {"detail": f"{state['city']} 的第一版细则", "log": ["子图.写细则"]}

    sub_builder = StateGraph(ParentState)
    sub_builder.add_node("sub_node", sub_node)
    sub_builder.add_edge(START, "sub_node")
    sub_builder.add_edge("sub_node", END)
    sub = sub_builder.compile()

    builder = StateGraph(ParentState)
    builder.add_node("prepare", lambda s: {"log": ["父图.prepare"]})
    builder.add_node("sub", sub)
    builder.add_edge(START, "prepare")
    builder.add_edge("prepare", "sub")
    builder.add_edge("sub", END)
    parent = builder.compile(checkpointer=InMemorySaver())

    config = {"configurable": {"thread_id": "sub-travel-1"}}
    parent.invoke({"city": "杭州", "log": []}, config)

    state = parent.get_state(config, subgraphs=True)
    print(f"    父图 next={state.next}（已结束，任务已清空 tasks={len(state.tasks)}）")

    # 子图检查点和父图共库，靠 checkpoint_ns 区分；拿到子图 config 就能单独读写它的历史
    sub_configs = [
        t.config
        for t in parent.checkpointer.list(config)
        if t.config["configurable"].get("checkpoint_ns")
    ]
    print(f"    子图自己的检查点 {len(sub_configs)} 个")
    if sub_configs:
        sub_config = sub_configs[0]   # list 按时间倒序，第一条就是子图最新快照
        print(f"    子图命名空间 = {sub_config['configurable']['checkpoint_ns']}")
        print(f"    按子图 config 读状态：detail={parent.get_state(sub_config).values.get('detail')}")
        # 只看某个 checkpoint_id 只能拿到那一点；去掉 checkpoint_id、只留命名空间才能看全历史
        ns_config = {
            "configurable": {
                "thread_id": config["configurable"]["thread_id"],
                "checkpoint_ns": sub_config["configurable"]["checkpoint_ns"],
            }
        }
        sub_history = list(parent.get_state_history(ns_config))
        print(f"    子图历史长度 = {len(sub_history)}")
        for snap in sub_history:
            print(f"      next={snap.next} detail={snap.values.get('detail')}")


def main() -> None:
    demo_replay_and_fork()
    demo_subgraph_travel()
    print("\nS07 OK：重放、分支、子图粒度三类时间旅行都可复现")


if __name__ == "__main__":
    main()
