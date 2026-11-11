"""s08 流式：节点级看流程，令牌级看打字机效果。

对应 day16 中段。验证点：
1. stream_mode="updates"：每个节点跑完吐一次
2. stream_mode="messages" + version="v2"：模型逐令牌吐
3. 多模式组合：一条流里同时拿 messages 和 updates
4. 用 metadata["langgraph_node"] 只保留某个节点的令牌
"""
import sys
from pathlib import Path
from typing import TypedDict

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from langgraph.graph import END, START, StateGraph

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.llm import llm  # noqa: E402


class State(TypedDict, total=False):
    topic: str
    joke: str
    poem: str


def build_graph():
    model = llm(max_tokens=120, temperature=0.6, streaming=True)

    def write_joke(state: State) -> dict:
        return {"joke": model.invoke(f"写一个关于{state['topic']}的冷笑话，30 字以内").content}

    def write_poem(state: State) -> dict:
        return {"poem": model.invoke(f"写两句关于{state['topic']}的诗，20 字以内").content}

    builder = StateGraph(State)
    builder.add_node("write_joke", write_joke)
    builder.add_node("write_poem", write_poem)
    builder.add_edge(START, "write_joke")
    builder.add_edge(START, "write_poem")
    builder.add_edge("write_joke", END)
    builder.add_edge("write_poem", END)
    return builder.compile()


def split_chunk(chunk):
    """兼容 v2 字典格式与旧元组格式。"""
    if isinstance(chunk, dict) and "type" in chunk:
        return chunk["type"], chunk["data"]
    return "messages", chunk


def demo_updates() -> None:
    print("[1] 节点级：stream_mode='updates'")
    graph = build_graph()
    for chunk in graph.stream({"topic": "猫"}, stream_mode="updates"):
        for node, update in chunk.items():
            print(f"    [{node}] keys={list(update)}")


def demo_messages() -> None:
    print("\n[2] 令牌级：stream_mode='messages' + version='v2'")
    graph = build_graph()
    token_count = 0
    printed = 0
    for chunk in graph.stream({"topic": "猫"}, stream_mode="messages", version="v2"):
        kind, data = split_chunk(chunk)
        if kind != "messages":
            continue
        msg, metadata = data
        token_count += 1
        if metadata.get("langgraph_node") == "write_joke" and printed < 24:
            print(msg.content, end="", flush=True)
            printed += 1
    print(f"\n    共收到 {token_count} 个消息块（两个节点交织）")


def demo_combo_and_filter() -> None:
    print("\n[3] 组合模式 + 按节点过滤")
    graph = build_graph()
    joke_tokens, poem_tokens, node_updates = [], [], []
    for chunk in graph.stream({"topic": "猫"}, stream_mode=["messages", "updates"], version="v2"):
        kind, data = split_chunk(chunk)
        if kind == "messages":
            msg, metadata = data
            node = metadata.get("langgraph_node")
            if node == "write_joke":
                joke_tokens.append(msg.content)
            elif node == "write_poem":
                poem_tokens.append(msg.content)
        elif kind == "updates":
            node_updates.extend(data.keys())
    print(f"    write_joke 令牌块 {len(joke_tokens)} 个；write_poem 令牌块 {len(poem_tokens)} 个")
    print(f"    节点更新事件 {sorted(set(node_updates))}")
    print(f"    笑话片段：{''.join(joke_tokens)[:40]}")


def main() -> None:
    demo_updates()
    demo_messages()
    demo_combo_and_filter()
    print("\nS08 OK：节点级、令牌级、组合与过滤四种流式读法都可用")


if __name__ == "__main__":
    main()
