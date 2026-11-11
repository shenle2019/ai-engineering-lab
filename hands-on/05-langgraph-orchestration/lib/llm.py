"""模型工厂：凭证只从环境变量读取，不落盘。

课件用的是 ChatOpenAI 兼容层接 DeepSeek，本实操沿用同一条路；
换模型只改 MODEL_NAME / BASE_URL 两个环境变量即可。
"""
import os

from langchain_openai import ChatOpenAI

BASE_URL = os.getenv("BASE_URL", "https://api.deepseek.com")
DEFAULT_MODEL = os.getenv("MODEL_NAME", "deepseek-chat")


def _key() -> str:
    key = (os.getenv("DEEPSEEK_API_KEY") or os.getenv("API_KEY") or "").strip()
    if not key:
        raise RuntimeError("缺少环境变量 DEEPSEEK_API_KEY，先设置再运行")
    return key


def llm(
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int | None = None,
    streaming: bool = False,
) -> ChatOpenAI:
    """返回一个指向 DeepSeek 的 ChatOpenAI 客户端。"""
    kwargs: dict = {}
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    return ChatOpenAI(
        model=model or DEFAULT_MODEL,
        api_key=_key(),
        base_url=BASE_URL,
        temperature=temperature,
        streaming=streaming,
        **kwargs,
    )


def structured(schema, model: str | None = None, temperature: float = 0):
    """结构化输出工厂。

    坑：with_structured_output() 默认 method="json_schema"，走 response_format=json_schema；
    DeepSeek 目前不支持这个 response_format，会直接 400 `This response_format type is
    unavailable now`。DeepSeek 支持 function calling，所以这里统一走 function_calling。
    换回 OpenAI/通义等支持 json_schema 的模型时，把 method 改回默认即可。
    """
    return llm(model=model, temperature=temperature).with_structured_output(
        schema, method="function_calling"
    )
