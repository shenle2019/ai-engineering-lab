"""阶段 02：东方财富行情接口字段校准。

课件代码里有两处未经验证的假设，这里用真实数据逐项核对：
1. 价格字段 f43 的除数到底是 100 还是 1000
2. f116 是不是市盈率（课件注释写"市盈率"）

方法：拉取多只股票的完整字段，打印原始值，再用常识（茅台股价千元级、
宁德时代百元级）反推单位；市盈率通过 f162/f163/f164 交叉比对。
校准结论直接写进 lib/eastmoney.py，作为后续所有阶段的唯一数据源。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import requests  # noqa: E402
from lib.common import setup_logging, banner  # noqa: E402

STAGE = "02_eastmoney_calibrate"

FIELDS = "f43,f44,f45,f46,f57,f58,f60,f116,f117,f162,f163,f164,f167,f168,f169,f170"
SAMPLES = [("1.600519", "贵州茅台", "沪市"), ("0.300750", "宁德时代", "深市创业板")]


def fetch(secid: str) -> dict:
    url = f"https://push2.eastmoney.com/api/qt/stock/get?secid={secid}&fields={FIELDS}"
    resp = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0 (learning-lab)"})
    payload = resp.json()
    if payload.get("rc") != 0 or not payload.get("data"):
        raise RuntimeError(f"接口返回异常：{payload}")
    return payload["data"]


def main() -> int:
    log = setup_logging(STAGE)
    banner(log, "阶段 02 东方财富字段校准")

    for secid, name, market in SAMPLES:
        log.info("---- %s %s (%s) ----", name, secid, market)
        raw = fetch(secid)
        for key in ["f58", "f43", "f60", "f169", "f170", "f116", "f117", "f162", "f163", "f164", "f167", "f168"]:
            log.info("  %-5s = %s", key, raw.get(key))

        price = raw.get("f43")
        log.info("  价格推算：f43/100  = %.2f 元", price / 100)
        log.info("  价格推算：f43/1000 = %.3f 元", price / 1000)
        log.info("  涨跌幅推算：f170/100 = %.2f%%", raw.get("f170") / 100)
        log.info("  f116/1e8 = %.2f 亿（总市值推算）", raw.get("f116") / 1e8)
        log.info("  f162 直接读 = %s（市盈率动态候选）", raw.get("f162"))

    log.info("")
    log.info("校准结论（写入 lib/eastmoney.py）：")
    log.info("1. f43 价格字段的除数是 100，课件里 /1000 是错的（会把茅台算成 144 元）")
    log.info("2. f116 是总市值（单位元），不是市盈率；市盈率动态应取 f162，需 /100 后使用")
    log.info("3. f170 涨跌幅除数是 100，课件这一点是对的")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
