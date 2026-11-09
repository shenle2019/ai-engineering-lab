"""DeepSeek 客户端封装：OpenAI 兼容协议。

凭证只从环境变量 DEEPSEEK_API_KEY 读取，不落盘、不写入仓库。
本机检测不到 key 时返回 None，调用方据此降级为协议层 mock。
"""
import os

from openai import OpenAI

BASE_URL = "https://api.deepseek.com/v1"
MODEL = "deepseek-chat"


def get_client():
    key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not key:
        return None
    return OpenAI(api_key=key, base_url=BASE_URL)
