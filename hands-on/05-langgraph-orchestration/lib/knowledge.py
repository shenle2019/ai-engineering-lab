"""离线知识库：把「事实与价格」交给代码，只把「文案」交给模型。

课件里景点/美食和费用全部由 LLM 生成，价格经常飘忽，预算判断随之不稳。
复刻时改成「知识库定事实、LLM 定表达」，预算路由才是可复现的。
"""

CITY_BOOK: dict[str, dict] = {
    "杭州": {
        "attractions": [
            {"name": "西湖环湖步道", "fee": 0, "hours": 3},
            {"name": "灵隐寺", "fee": 75, "hours": 3},
            {"name": "西溪湿地", "fee": 80, "hours": 4},
            {"name": "浙江省博物馆", "fee": 0, "hours": 2},
            {"name": "河坊街", "fee": 0, "hours": 2},
        ],
        "foods": [
            {"name": "片儿川", "price": 25},
            {"name": "葱包桧", "price": 12},
            {"name": "西湖醋鱼", "price": 88},
            {"name": "龙井虾仁", "price": 98},
        ],
        "hotel": 320,
    },
    "成都": {
        "attractions": [
            {"name": "武侯祠", "fee": 50, "hours": 3},
            {"name": "杜甫草堂", "fee": 50, "hours": 2},
            {"name": "宽窄巷子", "fee": 0, "hours": 2},
            {"name": "大熊猫繁育基地", "fee": 55, "hours": 4},
            {"name": "人民公园", "fee": 0, "hours": 2},
        ],
        "foods": [
            {"name": "担担面", "price": 15},
            {"name": "钟水饺", "price": 18},
            {"name": "火锅", "price": 120},
            {"name": "老妈兔头", "price": 35},
        ],
        "hotel": 280,
    },
    "西安": {
        "attractions": [
            {"name": "兵马俑", "fee": 120, "hours": 5},
            {"name": "陕西历史博物馆", "fee": 0, "hours": 3},
            {"name": "大雁塔", "fee": 50, "hours": 2},
            {"name": "城墙骑行", "fee": 45, "hours": 2},
            {"name": "回民街", "fee": 0, "hours": 2},
        ],
        "foods": [
            {"name": "肉夹馍", "price": 12},
            {"name": "凉皮", "price": 10},
            {"name": "羊肉泡馍", "price": 38},
            {"name": "葫芦鸡", "price": 78},
        ],
        "hotel": 300,
    },
}

DEFAULT_CITY = "杭州"


def load_city(city: str) -> dict:
    """未知城市退化为默认城市，保证 demo 永远可跑。"""
    return CITY_BOOK.get(city, CITY_BOOK[DEFAULT_CITY])


def estimate_cost(city: str, days: int, level: str = "standard") -> dict:
    """按「门票 + 餐饮 + 住宿」估一个可复现的价格区间。

    level: standard 常规；frugal 穷游（住宿对半、餐饮七折）。
    """
    book = load_city(city)
    hotel = book["hotel"] * (0.5 if level == "frugal" else 1.0)
    meals = sum(f["price"] for f in book["foods"]) * (0.7 if level == "frugal" else 1.0)
    tickets = sum(a["fee"] for a in book["attractions"])
    nights = max(days - 1, 1)
    total = round(hotel * nights + meals * days / 2 + tickets, 1)
    return {"hotel": hotel, "tickets": tickets, "meals": round(meals, 1), "total": total}
