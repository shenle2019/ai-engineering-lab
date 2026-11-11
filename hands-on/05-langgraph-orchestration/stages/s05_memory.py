"""s05 记忆：短期靠 checkpointer + thread_id，长期靠 store + user_id。

对应 day15 前半。验证点：
1. 同一 thread_id 第二轮能看到第一轮说的话；换 thread 就忘了
2. trim_messages 按条数修剪；RemoveMessage 可以清空消息
3. get_state_history 能回看每一步；delete_thread 后历史消失
4. 长期记忆用 (user_id, namespace) 做命名空间，跨 thread 仍能读到
"""
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, TypedDict

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    RemoveMessage,
    trim_messages,
)
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.message import REMOVE_ALL_MESSAGES, add_messages
from langgraph.runtime import Runtime
from langgraph.store.memory import InMemoryStore

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.llm import llm  # noqa: E402


@dataclass
class UserContext:
    user_id: str


def build_chat_graph():
    """一个最简对话图：每次把完整历史交给模型。"""
    model = llm(max_tokens=120, temperature=0.2)

    def chat(state: MessagesState) -> dict:
        return {"messages": [model.invoke(state["messages"])]}

    builder = StateGraph(MessagesState)
    builder.add_node("chat", chat)
    builder.add_edge(START, "chat")
    builder.add_edge("chat", END)
    return builder.compile(checkpointer=InMemorySaver())


def demo_short_term() -> None:
    print("[1] 短期记忆：thread_id 是记忆的开关")
    graph = build_chat_graph()
    config_a = {"configurable": {"thread_id": "user-a"}}

    graph.invoke({"messages": [HumanMessage(content="我叫阿远，喜欢穷游，记住。")]}, config_a)
    second = graph.invoke({"messages": [HumanMessage(content="我叫什么？喜欢什么？")]}, config_a)
    print(f"    同 thread 第二轮消息数 = {len(second['messages'])}（含历史）")
    print(f"    模型回答：{second['messages'][-1].content}")

    config_b = {"configurable": {"thread_id": "user-b"}}
    fresh = graph.invoke({"messages": [HumanMessage(content="我叫什么？")]}, config_b)
    print(f"    换 thread 第二轮消息数 = {len(fresh['messages'])}（只有本轮）")
    print(f"    模型回答：{fresh['messages'][-1].content}")

    print("\n[2] 检查点运维")
    history = list(graph.get_state_history(config_a))
    print(f"    user-a 共 {len(history)} 个检查点，最新 next={history[0].next}")
    graph.checkpointer.delete_thread("user-b")
    print(f"    删除 user-b 后历史数 = {len(list(graph.get_state_history(config_b)))}")


def demo_message_management() -> None:
    print("\n[3] 消息管理：修剪与删除")
    long_history = [
        HumanMessage(content=f"第{i}轮用户提问", id=str(i)) for i in range(1, 5)
    ] + [AIMessage(content=f"第{i}轮回答", id=f"a{i}") for i in range(1, 5)]
    trimmed = trim_messages(long_history, max_tokens=4, strategy="last", token_counter=len)
    print(f"    修剪前 {len(long_history)} 条 → 修剪后 {len(trimmed)} 条")

    class MsgState(TypedDict, total=False):
        # 坑：messages 必须用 add_messages 做 reducer，RemoveMessage 才会被当指令处理；
        # 用 operator.add 的话它只是一条普通消息，会被原样追加进列表。
        messages: Annotated[list, add_messages]

    def clear(state: MsgState) -> dict:
        # REMOVE_ALL_MESSAGES 是内置哨兵 id，等价于一次清空
        return {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES)]}

    builder = StateGraph(MsgState)
    builder.add_node("clear", clear)
    builder.add_edge(START, "clear")
    builder.add_edge("clear", END)
    result = builder.compile().invoke({"messages": [HumanMessage(content="会被清掉")]})
    print(f"    RemoveMessage 清空后消息数 = {len(result.get('messages', []))}")


def demo_long_term() -> None:
    print("\n[4] 长期记忆：store 的命名空间是 (user_id, 'profile')")
    store = InMemoryStore()

    class ProfileState(TypedDict, total=False):
        note: str
        recalled: str

    def remember(state: ProfileState, runtime: Runtime[UserContext]) -> dict:
        ns = (runtime.context.user_id, "profile")
        runtime.store.put(ns, str(uuid.uuid4()), {"text": state["note"]})
        return {}

    def recall(state: ProfileState, runtime: Runtime[UserContext]) -> dict:
        ns = (runtime.context.user_id, "profile")
        items = runtime.store.search(ns, limit=5)
        return {"recalled": "；".join(i.value["text"] for i in items)}

    builder = StateGraph(ProfileState, context_schema=UserContext)
    builder.add_node("remember", remember)
    builder.add_node("recall", recall)
    builder.add_edge(START, "remember")
    builder.add_edge("remember", "recall")
    builder.add_edge("recall", END)
    graph = builder.compile(checkpointer=InMemorySaver(), store=store)

    # 两次调用用不同 thread，但同一个 user_id：记忆仍然在
    graph.invoke(
        {"note": "喜欢穷游，预算敏感"},
        {"configurable": {"thread_id": "t1"}},
        context=UserContext(user_id="u42"),
    )
    out = graph.invoke(
        {"note": "这次想去西安"},
        {"configurable": {"thread_id": "t2"}},
        context=UserContext(user_id="u42"),
    )
    print(f"    t2 读到跨 thread 画像：{out['recalled']}")
    print(f"    store 内条目数 = {len(store.search(('u42', 'profile'), limit=10))}")


def main() -> None:
    demo_short_term()
    demo_message_management()
    demo_long_term()
    print("\nS05 OK：短期记忆隔离、消息修剪/清空、长期跨会话记忆都符合预期")


if __name__ == "__main__":
    main()
