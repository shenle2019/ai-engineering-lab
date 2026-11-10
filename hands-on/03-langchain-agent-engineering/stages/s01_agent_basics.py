"""阶段 1（对应 day03）：create_agent 三要素 + 动态提示词 + 基础结构化输出。

验证点：
1. 工具调用闭环：模型自己决定调 calc，框架执行并把结果回填
2. 动态提示词：同一个 Agent 按 invoke 传入的 context 改变系统提示
3. 结构化输出：response_format=ToolStrategy(Schema) 后从 structured_response 取结果

运行：在项目根目录执行
    python -m stages.s01_agent_basics
"""
import ast
import operator
from dataclasses import dataclass

from langchain.agents import create_agent
from langchain.agents.middleware import dynamic_prompt, ModelRequest
from langchain.agents.structured_output import ToolStrategy
from langchain.tools import tool
from pydantic import BaseModel, Field

from lib.llm import deepseek


# ---------- 工具：用 AST 做安全四则运算，不 eval ----------
_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}


def _eval_node(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval_node(node.operand))
    raise ValueError("只支持数字与 + - * / ** 运算")


@tool
def calc(expression: str) -> str:
    """计算数学表达式，例如 '128 * 0.85 + 12'。

    Args:
        expression: 只含数字、括号和 + - * / ** 的表达式
    """
    value = _eval_node(ast.parse(expression, mode="eval").body)
    return f"{expression} = {value}"


@tool
def get_course_price(course: str) -> str:
    """查询课程价格（元）。

    Args:
        course: 课程名，如 'langchain'、'langgraph'
    """
    prices = {"langchain": 499, "langgraph": 599, "fastmcp": 399}
    price = prices.get(course.lower())
    return f"{course} 价格 {price} 元" if price else f"没有找到课程 {course}"


# ---------- 动态提示词：context 里带用户身份 ----------
@dataclass
class SalesContext:
    user_name: str
    level: str


@dynamic_prompt
def level_aware_prompt(request: ModelRequest) -> str:
    ctx = request.runtime.context
    tone = "可以给 9 折报价" if ctx.level == "vip" else "按原价报价，不打折"
    return (
        f"你是课程顾问，正在服务 {ctx.user_name}（等级 {ctx.level}）。{tone}。"
        "报价前必须先用工具查价格，不要凭记忆编价格。回答控制在 60 字以内。"
    )


# ---------- 结构化输出 schema ----------
class Quote(BaseModel):
    """报价结果。"""

    user_name: str = Field(description="客户姓名")
    course: str = Field(description="课程名")
    list_price: int = Field(description="原价，单位元")
    final_price: int = Field(description="最终报价，单位元")


def main() -> None:
    model = deepseek(temperature=0.2)

    print("=" * 20, "1. 静态提示词 Agent：工具调用闭环", "=" * 20)
    agent = create_agent(
        model=model,
        tools=[calc, get_course_price],
        system_prompt="你是计算助手，涉及数学必须调用 calc 工具，不要心算。",
    )
    result = agent.invoke({"messages": [{"role": "user", "content": "帮我算一下 128*0.85+12"}]})
    for msg in result["messages"]:
        kind = type(msg).__name__
        if getattr(msg, "tool_calls", None):
            print(f"[{kind}] 决定调用工具: {[c['name'] for c in msg.tool_calls]}")
        elif kind == "ToolMessage":
            print(f"[{kind}] 工具返回: {msg.content}")
        elif msg.content:
            print(f"[{kind}] {msg.content}")

    print("=" * 20, "2. 动态提示词 Agent：按 context 改变行为", "=" * 20)
    dynamic_agent = create_agent(
        model=model,
        tools=[get_course_price],
        middleware=[level_aware_prompt],
        context_schema=SalesContext,
        response_format=ToolStrategy(Quote),
    )
    question = {"messages": [{"role": "user", "content": "我想买 langchain 课，多少钱？"}]}
    for level in ("vip", "normal"):
        ctx = SalesContext(user_name="张三", level=level)
        result = dynamic_agent.invoke(question, context=ctx)
        quote = result["structured_response"]
        print(f"[{level}] 文本回答: {result['messages'][-1].content}")
        print(f"[{level}] structured_response: {quote}")


if __name__ == "__main__":
    main()
