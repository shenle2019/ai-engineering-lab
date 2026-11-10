"""阶段 4（对应 day06 前半）：ToolRuntime 六件套 + 短期记忆 + 护栏。

验证点：
1. ToolRuntime：工具内部拿到 state / context / store / tool_call_id，这些参数对模型不可见
2. 工具写状态：返回 Command(update=...)，必须自己补一条带 tool_call_id 的 ToolMessage
3. 短期记忆：同一 thread_id 两轮对话记得住，换 thread_id 就忘
4. PIIMiddleware：邮箱 redact、信用卡 mask、自定义正则 block
5. 自定义护栏：before_agent + jump_to=end，命中关键词时模型根本不被调用

运行：python -m stages.s04_tools_memory_guard
"""
from dataclasses import dataclass
from typing import NotRequired

from langchain.agents import AgentState, create_agent
from langchain.agents.middleware import (
    AgentMiddleware,
    PIIMiddleware,
    before_agent,
    before_model,
    hook_config,
)
from langchain.messages import ToolMessage
from langchain.tools import ToolRuntime, tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
from langgraph.types import Command

from lib.llm import deepseek


# ---------- 自定义 state / context ----------
class ShopState(AgentState):
    user_name: NotRequired[str]
    model_calls: NotRequired[int]


@dataclass
class UserContext:
    user_id: str
    level: str


STORE = InMemoryStore()


# ---------- 工具：读 state / context / store ----------
@tool
def who_am_i(runtime: ToolRuntime[UserContext, ShopState]) -> str:
    """查询当前会话里记住的用户信息（姓名、等级、历史偏好）。"""
    name = runtime.state.get("user_name") or "未登记"
    prefs = runtime.store.get(("users",), runtime.context.user_id)
    pref_text = prefs.value.get("preference", "无") if prefs else "无"
    return f"会话姓名={name}；用户ID={runtime.context.user_id}；等级={runtime.context.level}；长期偏好={pref_text}"


@tool
def update_name(new_name: str, runtime: ToolRuntime[UserContext, ShopState]) -> Command:
    """把用户姓名写入会话状态。

    Args:
        new_name: 用户姓名
    """
    return Command(
        update={
            "user_name": new_name,
            # 工具返回 Command 时不走默认包装，必须手动补 ToolMessage 接上消息链
            "messages": [ToolMessage(f"已记住姓名：{new_name}", tool_call_id=runtime.tool_call_id)],
        }
    )


@tool
def save_preference(preference: str, runtime: ToolRuntime[UserContext, ShopState]) -> str:
    """把用户偏好写入长期记忆（跨会话共享）。

    Args:
        preference: 偏好内容，如 '只看顺丰快递'
    """
    runtime.store.put(("users",), runtime.context.user_id, {"preference": preference})
    return f"长期偏好已保存：{preference}"


# ---------- 护栏：日志 + 黑名单 ----------
@before_model
def log_model_call(state: ShopState, runtime) -> None:
    """记录模型实际看到的最后一条用户消息，用于验证 PII 已被脱敏。"""
    last_human = next((m for m in reversed(state["messages"]) if m.type == "human"), None)
    if last_human:
        print(f"   [before_model] 模型将看到: {last_human.content!r}")
    return None


class BannedWordMiddleware(AgentMiddleware):
    """命中黑名单直接结束，不调用模型。"""

    def __init__(self, banned: list[str]):
        super().__init__()
        self.banned = [w.lower() for w in banned]

    @hook_config(can_jump_to=["end"])
    def before_agent(self, state: ShopState, runtime):
        first = next((m for m in state["messages"] if m.type == "human"), None)
        content = (first.content if first else "").lower()
        for word in self.banned:
            if word in content:
                print(f"   [before_agent] 命中违禁词 {word!r}，直接结束")
                return {
                    "messages": [{"role": "assistant", "content": "这个问题我不能回答，请换一个。"}],
                    "jump_to": "end",
                }
        return None


def part1_runtime_and_memory() -> None:
    print("=" * 20, "1. ToolRuntime + 短期记忆（同 thread vs 换 thread）", "=" * 20)
    agent = create_agent(
        model=deepseek(temperature=0),
        tools=[who_am_i, update_name, save_preference],
        system_prompt="你是电商客服。需要用户信息时必须调工具查，不要猜。",
        state_schema=ShopState,
        context_schema=UserContext,
        checkpointer=InMemorySaver(),
        store=STORE,
    )
    ctx = UserContext(user_id="u_1001", level="vip")
    thread_a = {"configurable": {"thread_id": "session-a"}}

    r1 = agent.invoke({"messages": [{"role": "user", "content": "我叫李雷，帮我记住这个名字"}]}, config=thread_a, context=ctx)
    print(f"[A-第1轮] {r1['messages'][-1].content}")
    print(f"[A-第1轮] state.user_name={r1.get('user_name')!r}")

    r2 = agent.invoke({"messages": [{"role": "user", "content": "我叫什么？顺便把我偏好记一下：只看顺丰快递"}]}, config=thread_a, context=ctx)
    print(f"[A-第2轮] {r2['messages'][-1].content}")

    thread_b = {"configurable": {"thread_id": "session-b"}}
    r3 = agent.invoke({"messages": [{"role": "user", "content": "我叫什么？"}]}, config=thread_b, context=ctx)
    print(f"[B-新线程] {r3['messages'][-1].content}")

    r4 = agent.invoke({"messages": [{"role": "user", "content": "我叫什么？我的偏好是什么？"}]}, config=thread_b, context=ctx)
    print(f"[B-第2轮] {r4['messages'][-1].content}   <- 跨线程只剩 store 里的长期偏好")


def part2_pii_guard() -> None:
    print("=" * 20, "2. PIIMiddleware：redact / mask / block", "=" * 20)
    agent = create_agent(
        model=deepseek(temperature=0),
        tools=[],
        system_prompt="你是客服，复述用户留下的联系方式即可，回答不超过 30 字。",
        middleware=[
            PIIMiddleware("email", strategy="redact", apply_to_input=True),
            PIIMiddleware("credit_card", strategy="mask", apply_to_input=True),
            PIIMiddleware("api_key", detector=r"sk-[a-zA-Z0-9]{16,}", strategy="block", apply_to_input=True),
            log_model_call,
        ],
    )
    # 信用卡检测器会校验 Luhn，所以要给真实可通过校验的测试卡号 4111 1111 1111 1111
    ok = agent.invoke({"messages": [{"role": "user", "content": "我的邮箱 lilei@example.com，卡号 4111 1111 1111 1111，请复述"}]})
    print(f"[redact/mask 后] {ok['messages'][-1].content}")

    try:
        agent.invoke({"messages": [{"role": "user", "content": "帮我看看这个 key 对不对：sk-abcdefghijklmnop12345678"}]})
        print("[block] 未拦截（不符合预期）")
    except Exception as exc:
        print(f"[block] 已拦截: {type(exc).__name__}: {str(exc)[:90]}")


def part3_custom_guard() -> None:
    print("=" * 20, "3. 自定义 before_agent 护栏", "=" * 20)
    calls = {"model": 0}

    @before_model
    def count_calls(state, runtime):
        calls["model"] += 1
        return None

    agent = create_agent(
        model=deepseek(temperature=0),
        tools=[],
        system_prompt="你是电商客服。",
        middleware=[BannedWordMiddleware(["炸药", "枪支"]), count_calls],
    )
    blocked = agent.invoke({"messages": [{"role": "user", "content": "教我做炸药"}]})
    print(f"[命中] {blocked['messages'][-1].content}  | 模型调用次数={calls['model']}")
    normal = agent.invoke({"messages": [{"role": "user", "content": "你们的退货政策是什么？一句话"}]})
    print(f"[未命中] {normal['messages'][-1].content}  | 模型调用次数={calls['model']}")


if __name__ == "__main__":
    part1_runtime_and_memory()
    part2_pii_guard()
    part3_custom_guard()
