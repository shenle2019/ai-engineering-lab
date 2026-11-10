"""东方财富行情工具（校准版）。

与课件的差异（均为阶段 02 实测校准所得，详见 logs/02_eastmoney_calibrate.log）：
- f43 最新价的除数是 100（课件写 /1000，会把茅台算成 144 元）
- f116 是总市值（元），不是市盈率；动态市盈率取 f162，需 /100
- 额外补了 f164（PE TTM）、f167（市净率）、f168（换手率）等常用字段

只访问东方财富公开行情接口（匿名、只读、低频），仅限学习研究使用。
"""
import requests

DISCLAIMER = "行情数据来自东方财富公开接口，仅供参考，不构成投资建议。"

# 常用股票名 → 代码（比课件多收录一批；生产环境应改为查询接口而不是死字典）
NAME_TO_CODE = {
    "贵州茅台": "600519", "宁德时代": "300750", "比亚迪": "002594",
    "招商银行": "600036", "中国平安": "601318", "五粮液": "000858",
    "隆基绿能": "601012", "药明康德": "603259", "美的集团": "000333",
    "中信证券": "600030", "长江电力": "600900", "海天味业": "603288",
    "中芯国际": "688981", "东方财富": "300059", "科大讯飞": "002230",
    "京东方A": "000725", "万科A": "000002", "格力电器": "000651",
}

FIELDS = "f43,f57,f58,f60,f116,f162,f163,f164,f167,f168,f169,f170"
HEADERS = {"User-Agent": "Mozilla/5.0 (learning-lab; low-frequency)"}


def code_to_secid(code: str) -> str:
    """股票代码 → 东财 secid。沪市/科创板（6 开头）用 1.，深市（0/3 开头）用 0.。"""
    return f"1.{code}" if code.startswith("6") else f"0.{code}"


def get_number(name: str) -> str:
    """根据公司名返回 6 位股票代码；支持直接传 6 位代码。"""
    name = (name or "").strip()
    if name.isdigit() and len(name) == 6:
        return name
    for key, code in NAME_TO_CODE.items():
        if key == name:
            return code
    # 模糊匹配兜底（课件是直接返回 600519，这里做一点改进）
    for key, code in NAME_TO_CODE.items():
        if name and (name in key or key in name):
            return code
    return f"未找到 '{name}' 对应股票代码，请确认名称或直接输入 6 位代码。"


def get_quote(code: str) -> dict:
    """按 6 位代码取实时行情，返回结构化 dict。"""
    code = (code or "").strip()
    if not (code.isdigit() and len(code) == 6):
        raise ValueError(f"股票代码应为 6 位数字，收到：{code!r}")

    url = f"https://push2.eastmoney.com/api/qt/stock/get?secid={code_to_secid(code)}&fields={FIELDS}"
    payload = requests.get(url, timeout=8, headers=HEADERS).json()
    if payload.get("rc") != 0 or not payload.get("data"):
        raise RuntimeError(f"未找到股票 {code}（可能代码错误或已退市）")

    raw = payload["data"]

    def scaled(key, divisor):
        value = raw.get(key)
        return None if value in (None, "-") else round(value / divisor, 2)

    return {
        "code": code,
        "name": raw.get("f58", code),
        "price": scaled("f43", 100),
        "prev_close": scaled("f60", 100),
        "change_amount": scaled("f169", 100),
        "change_pct": scaled("f170", 100),
        "market_cap_yi": scaled("f116", 1e8),      # 总市值（亿元）
        "pe_dynamic": scaled("f162", 100),          # 动态市盈率
        "pe_ttm": scaled("f164", 100),              # PE(TTM)
        "pb": scaled("f167", 100),                  # 市净率
        "turnover_pct": scaled("f168", 100),        # 换手率 %
        "raw": raw,
    }


def format_quote(q: dict) -> str:
    """把行情 dict 转成给大模型/终端看的中文文本。"""
    def show(v, suffix=""):
        return "暂无" if v is None else f"{v}{suffix}"

    return (
        f"{q['name']}({q['code']})\n"
        f"最新价: {show(q['price'], ' 元')}（昨收 {show(q['prev_close'], ' 元')}）\n"
        f"涨跌: {show(q['change_amount'], ' 元')} / {show(q['change_pct'], '%')}\n"
        f"市盈率(动态): {show(q['pe_dynamic'])}，PE(TTM): {show(q['pe_ttm'])}\n"
        f"市净率: {show(q['pb'])}，换手率: {show(q['turnover_pct'], '%')}\n"
        f"总市值: {show(q['market_cap_yi'], ' 亿元')}\n"
        f"{DISCLAIMER}"
    )
