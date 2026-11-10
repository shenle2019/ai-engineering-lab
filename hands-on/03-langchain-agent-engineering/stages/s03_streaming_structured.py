"""阶段 3（对应 day05）：流式四种模式 + 结构化输出与自动纠错。

验证点：
1. updates：按节点拿进度（model / tools 各一步）
2. messages：拿 token 级增量，metadata 里带 langgraph_node
3. custom：工具内部用 get_stream_writer 主动上报进度
4. 多模式组合：stream_mode 传列表后变成 (mode, chunk) 二元组
5. 结构化输出：ToolStrategy 拿到 structured_response；故意给不可能的 schema 约束，
   用自定义 handle_errors 观察「校验失败 -> 反馈给模型 -> 重试」的链路

运行：python -m stages.s03_streaming_structured
"""
from typing import Literal

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain.tools import tool
from langgraph.config import get_stream_writer
from pydantic import BaseModel, Field, field_validator

from lib.llm import deepseek


@tool
def lookup_order(order_id: str) -> str:
    """查询订单状态。

    Args:
        order_id: 订单号，如 'A1001'
    """
    orders = {"A1001": "已发货", "A1002": "待付款", "A1003": "已签收"}
    return f"订单 {order_id}: {orders.get(order_id, '查无此单')}"


@tool
def sync_inventory(sku: str) -> str:
    """同步库存（模拟耗时任务），过程中用 stream_writer 上报进度。

    Args:
        sku: 商品编码
    """
    writer = get_stream_writer()
    for step in ("连接仓库", "拉取明细", "写回缓存"):
        writer(f"[custom] {sku} 同步进度: {step}")
    return f"{sku} 库存同步完成"


SYSTEM = "你是电商客服助手，回答控制在 40 字以内。"


def part1_updates(agent) -> None:
    print("=" * 20, "1. stream_mode='updates'（节点进度）", "=" * 20)
    for chunk in agent.stream(
        {"messages": [{"role": "user", "content": "帮我查订单 A1001 的状态"}]},
        stream_mode="updates",
    ):
        # 单模式时每次产出就是一个 {节点名: 状态片段} 字典
        for node, payload in chunk.items():
            msgs = payload.get("messages", []) if isinstance(payload, dict) else []
            summary = []
            for m in msgs:
                if getattr(m, "tool_calls", None):
                    summary.append(f"AI 决定调 {[c['name'] for c in m.tool_calls]}")
                elif type(m).__name__ == "ToolMessage":
                    summary.append(f"工具返回 {m.content}")
                elif getattr(m, "content", None):
                    summary.append(f"AI 输出 {str(m.content)[:40]}")
            print(f"[节点 {node}] {' | '.join(summary) or '状态更新'}")


def part2_messages(agent) -> None:
    print("=" * 20, "2. stream_mode='messages'（token 增量）", "=" * 20)
    token_count = 0
    hops = []
    for chunk, metadata in agent.stream(
        {"messages": [{"role": "user", "content": "订单 A1002 什么状态？"}]},
        stream_mode="messages",
    ):
        node = metadata.get("langgraph_node")
        if node not in hops:
            hops.append(node)
        if getattr(chunk, "content", None):
            token_count += 1
            if token_count <= 6:
                print(f"[{node}] 片段: {chunk.content!r}")
    print(f"经过节点: {hops}，收到非空 token 片段 {token_count} 个")


def part3_custom(agent) -> None:
    print("=" * 20, "3. stream_mode='custom'（工具主动上报）", "=" * 20)
    for chunk in agent.stream(
        {"messages": [{"role": "user", "content": "帮我同步 SKU-9 的库存"}]},
        stream_mode="custom",
    ):
        print(chunk)


def part4_multi(agent) -> None:
    print("=" * 20, "4. 多模式组合（列表 -> 二元组）", "=" * 20)
    for mode, chunk in agent.stream(
        {"messages": [{"role": "user", "content": "同步 SKU-7 库存，然后告诉我完成没有"}]},
        stream_mode=["updates", "custom"],
    ):
        if mode == "custom":
            print(f"(custom) {chunk}")
        else:
            print(f"(updates) 节点={list(chunk)}")


# ---------- 结构化输出与纠错 ----------
class Feedback(BaseModel):
    """客户满意度。"""

    score: int = Field(ge=1, le=5, description="满意度 1-5 分")
    comment: str = Field(description="一句话点评")

    @field_validator("comment")
    @classmethod
    def comment_too_long(cls, value: str) -> str:
        """这个约束不会出现在 JSON Schema 里，模型无从得知，只能靠校验失败后重试。"""
        if len(value) > 8:
            raise ValueError(f"comment 最多 8 个字符，当前 {len(value)} 个")
        return value


def part5_structured() -> None:
    print("=" * 20, "5. 结构化输出 + handle_errors 纠错链路", "=" * 20)
    attempts: list[str] = []

    def on_error(err: Exception) -> str:
        attempts.append(type(err).__name__)
        print(f"   [handle_errors 第 {len(attempts)} 次] {type(err).__name__}: {str(err)[:120]}")
        return "comment 字段最多 8 个字符，请压缩后重新调用工具"

    agent = create_agent(
        model=deepseek(temperature=0),
        tools=[],
        system_prompt="你是满意度回访助手。",
        response_format=ToolStrategy(Feedback, handle_errors=on_error),
    )
    try:
        result = agent.invoke({"messages": [{"role": "user", "content": "客户说这次体验还行，打 5 分吧，再写一句点评"}]})
        print(f"最终 structured_response: {result['structured_response']}")
    except Exception as exc:  # 重试耗尽后框架会抛异常，这本身也是验证点
        print(f"最终仍失败: {type(exc).__name__}: {str(exc)[:160]}")
    print(f"纠错回调触发 {len(attempts)} 次，异常类型序列: {attempts}")


def main() -> None:
    agent = create_agent(
        model=deepseek(temperature=0),
        tools=[lookup_order, sync_inventory],
        system_prompt=SYSTEM,
    )
    part1_updates(agent)
    part2_messages(agent)
    part3_custom(agent)
    part4_multi(agent)
    part5_structured()


if __name__ == "__main__":
    main()
