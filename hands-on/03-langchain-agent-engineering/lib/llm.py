"""模型工厂：DeepSeek 官方包（ChatDeepSeek）与 OpenAI 兼容层（ChatOpenAI）两条路。

凭证只从环境变量 DEEPSEEK_API_KEY 读取，不落盘、不写进仓库。
两条路的差别只在「思考模型的 reasoning_content」：官方包原生支持，
兼容层拿不到这一段，普通对话两者等价。
"""
import os

from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI

BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"


def _key() -> str:
    key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not key:
        raise RuntimeError("缺少环境变量 DEEPSEEK_API_KEY，先设置再运行")
    return key


def deepseek(model: str = DEFAULT_MODEL, temperature: float = 0.3, **kwargs) -> ChatDeepSeek:
    """官方包路径。streaming=False 可关闭模型级流式。"""
    return ChatDeepSeek(model=model, api_key=_key(), temperature=temperature, **kwargs)


def deepseek_compatible(model: str = DEFAULT_MODEL, temperature: float = 0.3, **kwargs) -> ChatOpenAI:
    """OpenAI 兼容层路径：同一个 DeepSeek 服务，走 /v1 兼容接口。"""
    return ChatOpenAI(
        model=model,
        api_key=_key(),
        base_url=f"{BASE_URL}/v1",
        temperature=temperature,
        **kwargs,
    )
