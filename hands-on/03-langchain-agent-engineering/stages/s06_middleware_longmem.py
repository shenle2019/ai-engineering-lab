"""阶段 6（对应 day07 前半）：中间件 + 长期记忆 + 上下文工程。

验证点：
1. 内置中间件：ToolRetryMiddleware 把失败一次的工具调用自动重试成功
2. 自定义类中间件：before_model/after_model 日志 + wrap_model_call 里 request.override 动态换模型
3. 长期记忆：store 的 put/get/search（namespace + key 结构）
4. 上下文工程：@dynamic_prompt 同时融合三类来源——短期记忆（消息条数）、
   长期记忆（store 偏好）、运行时 context（用户角色），并验证提示词真的变了

运行：python -m stages.s06_middleware_longmem
"""
import sys
from dataclasses import dataclass
from typing import NotRequired

from langchain.agents import AgentState, create_agent
from langchain.agents.middleware import (
    AgentMiddleware,
    ModelCallLimitMiddleware,
    ToolRetryMiddleware,
    dynamic_prompt,
    ModelRequest,
)
from langchain.tools import tool
from langgraph.store.memory import InMemoryStore

from lib.llm import deepseek

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


# ---------- 1. 内置中间件：工具失败自动重试 ----------
_flaky_calls = {"n": 0}


@tool
def flaky_stock(sku: str) -> str:
    """查询库存（第一次调用会模拟超时失败）。

    Args:
        sku: 商品编码
    """
    _flaky_calls["n"] += 1
    if _flaky_calls["n"] == 1:
        raise RuntimeError("库存服务超时（模拟）")
    return f"{sku} 库存 42 件（第 {_flaky_calls['n']} 次调用成功）"


def part1_builtin_retry() -> None:
    print("=" * 20, "1. ToolRetryMiddleware：失败自动重试", "=" * 20)
    agent = create_agent(
        model=deepseek(temperature=0),
        tools=[flaky_stock],
        system_prompt="你是库存助手，必须调用工具查询，不要编。",
        middleware=[
            ToolRetryMiddleware(max_retries=2, initial_delay=0.2, backoff_factor=1.0),
            ModelCallLimitMiddleware(run_limit=6),  # 兜底：防止工具重试把模型调用拖爆
        ],
    )
    result = agent.invoke({"messages": [{"role": "user", "content": "SKU-1 还有多少库存？"}]})
    print(f"[重试后] 工具实际被调用 {_flaky_calls['n']} 次")
    print(f"[重试后] 最终回答: {result['messages'][-1].content}")


# ---------- 2. 自定义类中间件：日志 + 动态换模型 ----------
class LoggingMiddleware(AgentMiddleware):
    def before_model(self, state, runtime):
        print(f"   [Logging.before_model] 本次请求带 {len(state['messages'])} 条消息")
        return None

    def after_model(self, state, runtime):
        last = state["messages"][-1]
        print(f"   [Logging.after_model] 模型返回 {type(last).__name__}，{len(str(last.content))} 字")
        return None


class DifficultyRouterMiddleware(AgentMiddleware):
    """按问题长度在轻量模型和思考模型之间切换。"""

    def wrap_model_call(self, request, handler):
        last_human = next((m for m in reversed(request.messages) if m.type == "human"), None)
        text = str(last_human.content) if last_human else ""
        if len(text) >= 20:
            chosen = "deepseek-reasoner"
        else:
            chosen = "deepseek-chat"
        print(f"   [Router] 问题长度 {len(text)} 字 -> 选择 {chosen}")
        return handler(request.override(model=deepseek(model=chosen, temperature=0)))


def part2_custom_middleware() -> None:
    print("=" * 20, "2. 自定义中间件：日志 + request.override 动态换模型", "=" * 20)
    agent = create_agent(
        model=deepseek(temperature=0),
        tools=[],
        system_prompt="你是电商客服，一句话回答。",
        middleware=[LoggingMiddleware(), DifficultyRouterMiddleware()],
    )
    short = agent.invoke({"messages": [{"role": "user", "content": "多久发货？"}]})
    print(f"[短问题] {short['messages'][-1].content}")
    long_q = "我买的商品昨天显示已发货，但是物流信息一直没更新，请问大概还要等多久才能收到，能不能帮我催一下快递"
    long = agent.invoke({"messages": [{"role": "user", "content": long_q}]})
    print(f"[长问题] {long['messages'][-1].content}")


# ---------- 3. 长期记忆 store ----------
STORE = InMemoryStore()
STORE.put(("users",), "u_2001", {"name": "韩梅梅", "preference": "只接受顺丰", "level": "gold"})
STORE.put(("users",), "u_2002", {"name": "李雷", "preference": "接受任何快递", "level": "normal"})
STORE.put(("faq",), "shipping", {"answer": "默认 48 小时内发货"})


def part3_store() -> None:
    print("=" * 20, "3. 长期记忆：namespace + key", "=" * 20)
    item = STORE.get(("users",), "u_2001")
    print(f"[get] ('users',)/u_2001 = {item.value if item else None}")
    print(f"[search] ('users',) 全部条目 = {[it.value['name'] for it in STORE.search(('users',))]}")
    print(f"[search] ('faq',) 全部条目 = {[it.value for it in STORE.search(('faq',))]}")


# ---------- 4. 上下文工程：三类来源注入动态提示词 ----------
@dataclass
class ChatContext:
    user_id: str
    role: str


class ContextState(AgentState):
    ask_count: NotRequired[int]


@dynamic_prompt
def engineered_prompt(request: ModelRequest) -> str:
    ctx = request.runtime.context
    profile = request.runtime.store.get(("users",), ctx.user_id)
    pref = profile.value.get("preference") if profile else "无记录"
    history_len = len(request.messages)
    return (
        "你是电商客服。以下是运行时拼装好的上下文，回答时要用到：\n"
        f"- 短期记忆：本会话已有 {history_len} 条消息\n"
        f"- 长期记忆：该用户偏好 = {pref}\n"
        f"- 运行时身份：role={ctx.role}\n"
        "回答控制在 50 字以内，如果用户问「你知道什么」就复述上面三条。"
    )


def part4_context_engineering() -> None:
    print("=" * 20, "4. 上下文工程：短期 + 长期 + runtime context", "=" * 20)
    agent = create_agent(
        model=deepseek(temperature=0),
        tools=[],
        middleware=[engineered_prompt],
        context_schema=ChatContext,
        store=STORE,
    )
    ctx = ChatContext(user_id="u_2001", role="售后专员")
    first = agent.invoke({"messages": [{"role": "user", "content": "你知道关于我的哪些信息？"}]}, context=ctx)
    print(f"[第1次] {first['messages'][-1].content}")
    ctx2 = ChatContext(user_id="u_2002", role="普通客服")
    second = agent.invoke({"messages": [{"role": "user", "content": "你知道关于我的哪些信息？"}]}, context=ctx2)
    print(f"[换用户后] {second['messages'][-1].content}")


if __name__ == "__main__":
    part1_builtin_retry()
    part2_custom_middleware()
    part3_store()
    part4_context_engineering()
