"""综合案例：电商售后智能客服（把 day03–day07 的能力串成一条业务线）。

链路：
    输入护栏（PII redact + 违禁词）
      -> 动态提示词（短期记忆条数 + 长期偏好 + runtime context）
      -> 主管 Agent（多智能体：政策问题交给售后专家工具）
      -> 危险工具 refund 走 HITL，人工批准后才执行
      -> 长期记忆 store 记住用户偏好，换会话仍生效
      -> 最后用结构化输出生成工单摘要

运行：python -m case.customer_service_agent
"""
import sys
from dataclasses import dataclass
from typing import Literal, NotRequired

from langchain.agents import AgentState, create_agent
from langchain.agents.middleware import (
    AgentMiddleware,
    HumanInTheLoopMiddleware,
    PIIMiddleware,
    dynamic_prompt,
    hook_config,
    ModelRequest,
)
from langchain.agents.structured_output import ToolStrategy
from langchain.tools import ToolRuntime, tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
from langgraph.types import Command
from pydantic import BaseModel, Field

from lib.llm import deepseek

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

MODEL = deepseek(temperature=0)
STORE = InMemoryStore()
REFUNDS: list[str] = []


class CSState(AgentState):
    user_name: NotRequired[str]


@dataclass
class CSContext:
    user_id: str


# ---------- 护栏 ----------
class BannedWordGuard(AgentMiddleware):
    def __init__(self, banned: list[str]):
        super().__init__()
        self.banned = banned

    @hook_config(can_jump_to=["end"])
    def before_agent(self, state, runtime):
        text = " ".join(str(m.content) for m in state["messages"] if m.type == "human")
        if any(w in text for w in self.banned):
            return {
                "messages": [{"role": "assistant", "content": "这个问题超出客服范围，我无法回答。"}],
                "jump_to": "end",
            }
        return None


@dynamic_prompt
def service_prompt(request: ModelRequest) -> str:
    ctx = request.runtime.context
    profile = request.runtime.store.get(("users",), ctx.user_id)
    pref = profile.value.get("preference") if profile else "暂无记录"
    return (
        f"你是电商客服小服，当前用户 {ctx.user_id}，长期偏好：{pref}。\n"
        "规则：\n"
        "1. 退款/订单问题先调 query_order，再调 refund 发起退款（需人工审批）\n"
        "2. 退货政策、售后规则类咨询交给 policy_expert 回答\n"
        "3. 用户表达偏好时调用 save_preference 记录\n"
        "4. 每次回答不超过 60 字"
    )


# ---------- 工具 ----------
@tool
def query_order(order_id: str) -> str:
    """查询订单金额与状态。

    Args:
        order_id: 订单号
    """
    return f"订单 {order_id}: 268 元, 已签收"


@tool
def refund(order_id: str, amount: int) -> str:
    """发起退款（危险操作，必须人工审批）。

    Args:
        order_id: 订单号
        amount: 退款金额
    """
    REFUNDS.append(f"{order_id}:{amount}")
    return f"已原路退款 {amount} 元（订单 {order_id}）"


@tool
def save_preference(preference: str, runtime: ToolRuntime[CSContext, CSState]) -> str:
    """记录用户长期偏好（跨会话生效）。

    Args:
        preference: 偏好内容
    """
    runtime.store.put(("users",), runtime.context.user_id, {"preference": preference})
    return f"已记录偏好：{preference}"


policy_agent = create_agent(
    model=MODEL,
    tools=[],
    system_prompt="你是售后政策专家，只回答退货、换货、保修政策，60 字以内。",
    name="policy_expert_agent",
)


@tool("policy_expert", description="售后政策专家：退货、换货、保修规则的咨询")
def policy_expert(question: str) -> str:
    result = policy_agent.invoke({"messages": [{"role": "user", "content": question}]})
    return result["messages"][-1].content


def build_agent():
    return create_agent(
        model=MODEL,
        tools=[query_order, refund, save_preference, policy_expert],
        middleware=[
            PIIMiddleware("email", strategy="redact", apply_to_input=True),
            BannedWordGuard(["炸药"]),
            service_prompt,
            HumanInTheLoopMiddleware(
                interrupt_on={"refund": {"allowed_decisions": ["approve", "reject"]}},
                description_prefix="[财务审批] 退款待确认:",
            ),
        ],
        state_schema=CSState,
        context_schema=CSContext,
        store=STORE,
        checkpointer=InMemorySaver(),
    )


def print_steps(result) -> None:
    for m in result["messages"]:
        if getattr(m, "tool_calls", None):
            print(f"   [决策] 调用 {[c['name'] for c in m.tool_calls]}")
        elif m.type == "tool":
            print(f"   [工具] {m.content}")


def turn1_refund(agent) -> None:
    print("=" * 18, "第 1 轮：退款（触发 HITL 审批）", "=" * 18)
    config = {"configurable": {"thread_id": "cs-001"}}
    ctx = CSContext(user_id="u_9001")
    result = agent.invoke(
        {"messages": [{"role": "user", "content": "我是韩梅梅，订单 A1001 要退款 268 元，邮箱 han@example.com"}]},
        config=config,
        context=ctx,
    )
    print_steps(result)
    if "__interrupt__" in result:
        print(f"   [HITL] 命中审批，退款记录={REFUNDS}")
        result = agent.invoke(Command(resume={"decisions": [{"type": "approve"}]}), config=config, context=ctx)
        print(f"   [HITL] 人工批准后，退款记录={REFUNDS}")
    print(f"[客服] {result['messages'][-1].content}")


def turn2_preference(agent) -> None:
    print("=" * 18, "第 2 轮：记录偏好（流式观察过程）", "=" * 18)
    config = {"configurable": {"thread_id": "cs-001"}}
    ctx = CSContext(user_id="u_9001")
    final = None
    for chunk in agent.stream(
        {"messages": [{"role": "user", "content": "以后推荐课程只推 Python 方向的，帮我记一下"}]},
        config=config,
        context=ctx,
        stream_mode="updates",
    ):
        for node, payload in chunk.items():
            msgs = payload.get("messages", []) if isinstance(payload, dict) else []
            for m in msgs:
                if getattr(m, "tool_calls", None):
                    print(f"   [{node}] 调用 {[c['name'] for c in m.tool_calls]}")
                elif m.type == "tool":
                    print(f"   [{node}] 工具返回 {m.content}")
                elif m.type == "ai" and m.content:
                    final = m.content
    print(f"[客服] {final}")
    print(f"[长期记忆] store 中记录 = {STORE.get(('users',), 'u_9001').value}")


def turn3_policy(agent) -> None:
    print("=" * 18, "第 3 轮：换新会话问政策（多智能体 + 长期记忆）", "=" * 18)
    config = {"configurable": {"thread_id": "cs-002"}}
    ctx = CSContext(user_id="u_9001")
    result = agent.invoke({"messages": [{"role": "user", "content": "我买的课不想要了，退货政策怎么规定的？"}]}, config=config, context=ctx)
    print_steps(result)
    print(f"[客服] {result['messages'][-1].content}")


class Ticket(BaseModel):
    """工单摘要。"""

    user_name: str = Field(description="用户姓名")
    intent: Literal["售前", "售后", "其他"] = Field(description="意图分类")
    resolution: str = Field(description="处理结论，30 字以内")


def make_ticket(transcript: str) -> None:
    print("=" * 18, "第 4 轮：结构化输出生成工单", "=" * 18)
    summarizer = create_agent(
        model=MODEL,
        tools=[],
        system_prompt="你是工单系统，根据对话生成结构化摘要。",
        response_format=ToolStrategy(Ticket),
    )
    result = summarizer.invoke({"messages": [{"role": "user", "content": f"对话记录：\n{transcript}"}]})
    print(f"[工单] {result['structured_response']}")


if __name__ == "__main__":
    agent = build_agent()
    turn1_refund(agent)
    turn2_preference(agent)
    turn3_policy(agent)
    make_ticket("用户韩梅梅为订单 A1001 申请退款 268 元，已审批通过；偏好 Python 方向课程。")
