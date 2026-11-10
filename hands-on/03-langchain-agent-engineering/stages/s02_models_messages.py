"""阶段 2（对应 day04）：Models 模型接入 + 裸 Tool Calling 循环 + Messages 消息体系。

验证点：
1. 同一个 DeepSeek 服务，官方包与 OpenAI 兼容层都能对话，并拿到 usage_metadata
2. 不用 Agent，手写「bind_tools → tool_calls → 执行 → ToolMessage 回填 → 再请求」循环
3. 四类消息的构造、content_blocks 形态、AIMessageChunk 可相加
4. 可配置模型：init_chat_model + configurable_fields，调用时切模型/温度

运行：python -m stages.s02_models_messages
"""
import json

from langchain.chat_models import init_chat_model
from langchain.messages import AIMessage, AIMessageChunk, HumanMessage, SystemMessage, ToolMessage
from langchain.tools import tool

from lib.llm import deepseek, deepseek_compatible


@tool
def calc(expression: str) -> str:
    """计算数学表达式，只支持数字与 + - * / **。"""
    allowed = set("0123456789+-*/(). ")
    if not set(expression) <= allowed:
        raise ValueError(f"表达式含不允许字符: {expression}")
    return f"{expression} = {eval(expression)}"  # 输入已按字符白名单过滤


def part1_two_ways() -> None:
    print("=" * 20, "1. 官方包 vs OpenAI 兼容层", "=" * 20)
    prompt = "用一句话说明 LangChain 是什么"
    for name, model in (("ChatDeepSeek", deepseek(temperature=0)), ("ChatOpenAI(兼容)", deepseek_compatible(temperature=0))):
        reply = model.invoke(prompt)
        usage = reply.usage_metadata or {}
        print(f"[{name}] {reply.content}")
        print(f"[{name}] usage: input={usage.get('input_tokens')} output={usage.get('output_tokens')}")
        print(f"[{name}] 生成模型: {reply.response_metadata.get('model_name')}")


def part2_manual_tool_loop() -> None:
    print("=" * 20, "2. 裸 Model 的工具调用循环", "=" * 20)
    model = deepseek(temperature=0).bind_tools([calc])
    messages = [HumanMessage("先算 256*0.75，再把结果加 18，只用工具算，不要心算")]
    for round_no in range(1, 5):
        ai = model.invoke(messages)
        messages.append(ai)
        if not ai.tool_calls:
            print(f"[第 {round_no} 轮] 模型不再调工具，给出最终答案: {ai.content}")
            break
        for call in ai.tool_calls:
            print(f"[第 {round_no} 轮] tool_call: name={call['name']} args={call['args']} id={call['id']}")
            tool_result = calc.invoke(call)
            messages.append(tool_result)
            print(f"[第 {round_no} 轮] 回填 {type(tool_result).__name__}: {tool_result.content}")
    print(f"消息链结构: {' -> '.join(type(m).__name__ for m in messages)}")


def part3_messages() -> None:
    print("=" * 20, "3. Messages 体系", "=" * 20)
    system = SystemMessage("你是严谨的助教")
    human = HumanMessage("记住暗号 42", name="学员张三")
    ai = AIMessage("已记住")
    tool_msg = ToolMessage("已完成计算", tool_call_id="call_1", artifact={"raw": [1, 2, 3]})
    for msg in (system, human, ai, tool_msg):
        print(f"[{type(msg).__name__}] role={msg.type} content={msg.content!r}")

    chunk = AIMessageChunk(content="Lang") + AIMessageChunk(content="Chain")
    print(f"[AIMessageChunk] 分片相加 -> {chunk.content!r}")

    blocks = AIMessage(
        content_blocks=[
            {"type": "text", "text": "结论如下"},
            {"type": "tool_call", "name": "calc", "args": {"expression": "1+1"}, "id": "call_9"},
        ]
    )
    print("[content_blocks] 类型清单:", [b["type"] for b in blocks.content_blocks])


def part4_configurable_model() -> None:
    print("=" * 20, "4. 可配置模型（config_prefix 前缀）", "=" * 20)
    flex = init_chat_model(
        "deepseek:deepseek-chat",
        temperature=0.0,
        config_prefix="first",
        configurable_fields=("model", "temperature"),
    )
    result = flex.invoke(
        "只回答一个字：好",
        config={"configurable": {"first_model": "deepseek-reasoner", "first_temperature": 0.6}},
    )
    print(f"[切换后] content={result.content!r}")
    print(f"[切换后] 实际模型={result.response_metadata.get('model_name')}")
    print(f"[切换后] content_blocks 类型={[b['type'] for b in result.content_blocks]}")
    print(f"[切换后] additional_kwargs 键={list(result.additional_kwargs)}")


if __name__ == "__main__":
    part1_two_ways()
    part2_manual_tool_loop()
    part3_messages()
    part4_configurable_model()
    print("\n全部验证完成:", json.dumps({"stage": "s02", "ok": True}, ensure_ascii=False))
