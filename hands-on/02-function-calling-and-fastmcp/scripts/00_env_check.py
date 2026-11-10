"""阶段 00：环境预检。

检查四件事：
1. Python 版本与依赖（fastmcp / openai / requests / dotenv）
2. 东方财富行情接口连通性（匿名公开接口，不需要 key）
3. LLM 凭证是否就绪（只读环境变量，不落盘、不打印明文）
4. 最小 LLM 对话调用，确认 key 与网络都可用

结论写进日志：LLM 可用则后续阶段走真实大模型；不可用则降级为协议层 mock，
并在 README 的验证矩阵里如实标注。
"""
import os
import sys
import platform
from pathlib import Path

# 允许从任意工作目录运行：把实操根目录加进 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.common import setup_logging, banner  # noqa: E402

STAGE = "00_env_check"


def main() -> int:
    log = setup_logging(STAGE)
    banner(log, "阶段 00 环境预检")
    log.info("python: %s (%s)", sys.version.split()[0], platform.platform())

    if sys.version_info < (3, 10):
        log.error("FastMCP 需要 Python >= 3.10，当前 %s 不可用", sys.version.split()[0])
        return 1
    log.info("[OK] Python 版本满足 >= 3.10")

    # 1. 依赖
    import fastmcp
    import openai
    import requests
    from importlib.metadata import version

    log.info("[OK] fastmcp %s / mcp SDK 已安装", fastmcp.__version__)
    log.info("[OK] openai %s / requests %s / python-dotenv %s",
             openai.__version__, requests.__version__, version("python-dotenv"))

    # 2. 东方财富行情接口（匿名公开数据）
    url = "https://push2.eastmoney.com/api/qt/stock/get?secid=1.600519&fields=f43,f58,f170"
    resp = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0 (learning-lab)"})
    data = resp.json()
    if data.get("rc") != 0:
        log.error("[FAIL] 东方财富接口返回异常 rc=%s", data.get("rc"))
        return 1
    stock = data["data"]
    log.info("[OK] 东方财富接口连通，样本：%s 最新价原始值=%s 涨跌幅原始值=%s",
             stock.get("f58"), stock.get("f43"), stock.get("f170"))

    # 3. LLM 凭证（只报告存在性与长度，不打印明文）
    key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if key:
        log.info("[OK] 检测到 DEEPSEEK_API_KEY（长度 %d，前 4 位 %s****）", len(key), key[:4])
    else:
        log.warning("[WARN] 未检测到 DEEPSEEK_API_KEY，后续 LLM 阶段将降级为协议层 mock")

    # 4. 最小 LLM 调用
    if key:
        try:
            client = openai.OpenAI(api_key=key, base_url="https://api.deepseek.com/v1")
            resp = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": "只回复两个字：可用"}],
                max_tokens=10,
                temperature=0,
            )
            text = resp.choices[0].message.content
            log.info("[OK] DeepSeek 对话调用成功，模型回复：%s", (text or "").strip())
        except Exception as exc:  # noqa: BLE001
            log.warning("[WARN] DeepSeek 调用失败：%s —— 后续降级为协议层 mock", exc)
    else:
        log.warning("[WARN] 跳过真实 LLM 调用")

    log.info("阶段 00 预检完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
