"""阶段 01：Function Calling 七步流程真跑（DeepSeek + 东方财富）。

验证点：
1. tools 说明书传给模型后，模型返回结构化 tool_calls（函数名 + JSON 参数）
2. 反射调用映射表能把"函数名字符串"落到真实函数上执行
3. 第二次请求必须同时带 assistant 的 tool_calls 消息与 role=tool 的 tool_call_id
   —— 这里专门构造一次"漏掉 assistant 消息"的反例，看模型怎么报错
4. 多轮对话里 messages 累积后，模型能接着上文继续调工具

无 DEEPSEEK_API_KEY 时自动降级为协议层 mock（用构造的 tool_calls 对象走同一套
执行链路），日志与 README 会明确标注"mock"，不冒充真实模型验证。
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.common import setup_logging, banner  # noqa: E402
from lib.eastmoney import get_number, get_quote, format_quote  # noqa: E402
from lib.llm import get_client, MODEL  # noqa: E402

STAGE = "01_function_calling"

SYSTEM_PROMPT = (
    "你是股票助手。查询实时行情必须调用工具，不要凭记忆回答；"
    "如果用户只给了公司名，先用 get_number 查代码再查行情。回答用中文，简洁。"
)

# 第 1 步：工具函数（真实函数，工具本体）
# get_number / get_quote 来自 lib.eastmoney


def get_stock_info(code: str) -> str:
    """按 6 位股票代码查询最新价、涨跌幅、市盈率、市净率、总市值。"""
    return format_quote(get_quote(code))


# 第 2 步：说明书 tools（给模型看的接口文档）
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_number",
            "description": "通过公司中文名查询 6 位股票代码，例如 贵州茅台 -> 600519",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "公司中文名，如'贵州茅台'"}
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock_info",
            "description": "根据 6 位股票代码查询 A 股实时行情：最新价、涨跌幅、市盈率、市净率、总市值",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "6 位股票代码，如'600519'"}
                },
                "required": ["code"],
            },
        },
    },
]

# 第 5 步的前置：名字 → 真函数 的映射表（反射调用）
FUNCTION_MAP = {"get_number": get_number, "get_stock_info": get_stock_info}


def mock_first_response(user_text: str):
    """无 key 时的协议层 mock：构造与 OpenAI 同构的带 tool_calls 的响应。"""
    code = "600519"
    name = "贵州茅台"
    calls = [
        SimpleNamespace(id="call_mock_1", type="function",
                        function=SimpleNamespace(name="get_number", arguments=json.dumps({"name": name}, ensure_ascii=False))),
        SimpleNamespace(id="call_mock_2", type="function",
                        function=SimpleNamespace(name="get_stock_info", arguments=json.dumps({"code": code}, ensure_ascii=False))),
    ]
    message = SimpleNamespace(content="", tool_calls=calls,
                              model_dump=lambda: {"role": "assistant", "content": "", "tool_calls": [
                                  {"id": c.id, "type": "function",
                                   "function": {"name": c.function.name, "arguments": c.function.arguments}}
                                  for c in calls]})
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def run_turn(log, client, messages, user_text, max_steps=5):
    """一轮完整对话：提问 → 模型决策 → 反射执行 → 结果回传 → …… → 模型总结。

    关键点：每一次请求都要带 tools=tools。DeepSeek 在未传 tools 的请求里
    会把调用意图写成 <｜｜DSML｜｜> 文本而不是结构化 tool_calls（实测踩坑）。
    多跳任务（先查代码再查行情）靠循环执行到模型不再调工具为止。
    """
    log.info("")
    log.info(">>> 用户：%s", user_text)
    messages.append({"role": "user", "content": user_text})

    if not client:
        # mock：构造一次 tool_calls，执行后按协议回填，不再请求模型
        log.info("[MOCK] 无 API key，使用构造的 tool_calls 走协议层流程")
        msg = mock_first_response(user_text).choices[0].message
        log.info("模型第一次返回 %d 个 tool_call：", len(msg.tool_calls))
        messages.append(msg.model_dump())
        for call in msg.tool_calls:
            args = json.loads(call.function.arguments)
            result = FUNCTION_MAP[call.function.name](**args)
            log.info("  反射调用：%s(%s) -> %s", call.function.name, args, str(result)[:80])
            messages.append({"role": "tool", "tool_call_id": call.id, "content": str(result)})
        return "（mock 模式，未调用真实模型）"

    for step in range(1, max_steps + 1):
        # 每一次请求都带上 tools，否则模型无法以结构化方式继续调工具
        resp = client.chat.completions.create(
            model=MODEL, messages=messages, tools=tools, tool_choice="auto")
        msg = resp.choices[0].message

        if not getattr(msg, "tool_calls", None):
            answer = msg.content or ""
            messages.append({"role": "assistant", "content": answer})
            log.info(">>> 第 %d 跳：模型不再调工具，最终回答：", step)
            log.info("    %s", answer.replace("\n", "\n    "))
            return answer

        log.info("第 %d 跳：模型返回 %d 个 tool_call", step, len(msg.tool_calls))
        for call in msg.tool_calls:
            log.info("  - id=%s  name=%s  arguments=%s",
                     call.id, call.function.name, call.function.arguments)

        # 先把 assistant 的 tool_calls 消息原样放回对话（漏掉必 400）
        messages.append(msg.model_dump())

        for call in msg.tool_calls:
            name = call.function.name
            args = json.loads(call.function.arguments)
            func = FUNCTION_MAP.get(name)
            result = func(**args) if func else f"未知工具 {name}"
            log.info("  反射调用：%s(%s) -> %s", name, args, str(result)[:100].replace("\n", " | "))
            messages.append({"role": "tool", "tool_call_id": call.id, "content": str(result)})

    log.warning("超过最大跳数 %d，任务未收敛", max_steps)
    return ""


def demo_missing_assistant_message(log, client, messages):
    """反例验证：只发 user + tool 消息、不带 assistant tool_calls，观察模型报错。"""
    if not client:
        log.info("[MOCK] 无反例验证（需要真实模型）")
        return

    log.info("")
    log.info("---- 反例验证：漏掉 assistant 的 tool_calls 消息 ----")
    bad_messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "查一下贵州茅台行情"},
        {"role": "tool", "tool_call_id": "call_not_exist", "content": "贵州茅台(600519) 最新价 1444.99 元"},
    ]
    try:
        client.chat.completions.create(model=MODEL, messages=bad_messages)
        log.warning("反例居然成功了——说明该模型对消息结构校验较宽松，坑仍存在于其他模型")
    except Exception as exc:  # noqa: BLE001
        log.info("[OK] 模型按预期拒绝：%s", str(exc).replace("\n", " ")[:300])
        log.info("[OK] 反例验证成立：tool_call_id 对应的 assistant 消息缺失时请求失败")


def main() -> int:
    log = setup_logging(STAGE)
    banner(log, "阶段 01 Function Calling 七步流程")
    client = get_client()
    log.info("LLM 模式：%s", f"真实调用 {MODEL}" if client else "协议层 mock（无 key）")

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    answer1 = run_turn(log, client, messages, "贵州茅台现在股价多少？市盈率和总市值呢？")
    if client:
        # 第 4 条验证：多轮累积后继续调工具
        answer2 = run_turn(log, client, messages, "那宁德时代呢？只要最新价和涨跌幅。")
        demo_missing_assistant_message(log, client, messages)
    else:
        answer2 = ""

    # 消息结构自检：打印最终 messages 的角色序列，作为"七步链路"证据
    log.info("")
    log.info("最终 messages 角色序列：")
    for i, m in enumerate(messages):
        extra = ""
        if m.get("tool_calls"):
            extra = f" tool_calls={[c['function']['name'] for c in m['tool_calls']]}"
        if m.get("tool_call_id"):
            extra = f" tool_call_id={m['tool_call_id']}"
        content = (m.get("content") or "").replace("\n", " ")[:60]
        log.info("  [%d] %-9s%s | %s", i, m["role"], extra, content)

    ok = True
    if client:
        ok = bool(answer1 and answer2)
        log.info("最终答案1：%s", answer1.replace("\n", " ")[:150])
        log.info("最终答案2：%s", answer2.replace("\n", " ")[:150])
    log.info("阶段 01 %s", "完成" if ok else "未完成")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
