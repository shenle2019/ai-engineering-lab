"""节点实现：每个节点只做一件事，返回要合并进状态的字段。

约定：
- 只读 state，不改 state（返回新 dict 由 LangGraph 合并）
- 费用由 knowledge 里的确定性数据算出，文案才交给 LLM
"""
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.runtime import Runtime
from langgraph.types import interrupt

from .knowledge import estimate_cost, load_city
from .llm import llm
from .state import TravelState, UserContext

SYSTEM = "你是严谨的旅行规划师，输出中文、口语化、不加开场白。"


def _store(runtime) -> object | None:
    return getattr(runtime, "store", None)


def _user_id(runtime) -> str:
    ctx = getattr(runtime, "context", None)
    return getattr(ctx, "user_id", None) or "demo-user"


def load_profile(state: TravelState, runtime: Runtime[UserContext]) -> dict:
    """长期记忆：按 user_id 读历史画像，与 thread_id 无关。"""
    store = _store(runtime)
    profile = "暂无历史偏好"
    if store is not None:
        try:
            items = store.search((_user_id(runtime), "profile"), limit=3)
            if items:
                profile = "；".join(str(i.value.get("text", "")) for i in items)
        except Exception as exc:  # 存储后端不支持检索时降级
            profile = f"画像读取失败：{exc}"
    return {"profile": profile, "trace": [f"load_profile → 画像：{profile[:40]}"]}


def plan_attractions(state: TravelState) -> dict:
    """景点规划师：候选景点来自知识库，模型只负责排布和文案。"""
    req = state["request"]
    book = load_city(req["city"])
    names = "、".join(a["name"] for a in book["attractions"])
    prompt = (
        f"城市：{req['city']}，天数：{req['days']}，用户偏好：{req['preference']}。\n"
        f"只能从这些景点里选：{names}。\n"
        "请按天排出游玩顺序，说明为什么这样排，控制在 120 字以内。"
    )
    text = llm(max_tokens=260).invoke([SystemMessage(content=SYSTEM), HumanMessage(content=prompt)]).content
    tickets = sum(a["fee"] for a in book["attractions"])
    return {
        "attractions": text.strip(),
        "attraction_cost": float(tickets),
        "trace": [f"plan_attractions → 门票合计 {tickets} 元"],
    }


def plan_food(state: TravelState) -> dict:
    """美食规划师：餐厅与人均来自知识库。"""
    req = state["request"]
    book = load_city(req["city"])
    names = "、".join(f"{f['name']}(人均{f['price']}元)" for f in book["foods"])
    prompt = (
        f"城市：{req['city']}，天数：{req['days']}，偏好：{req['preference']}。\n"
        f"只能推荐这些：{names}。\n"
        "请分配到每天，给出 2 句推荐理由，控制在 100 字以内。"
    )
    text = llm(max_tokens=220).invoke([SystemMessage(content=SYSTEM), HumanMessage(content=prompt)]).content
    meals = sum(f["price"] for f in book["foods"]) * req["days"] / 2
    return {
        "foods": text.strip(),
        "food_cost": round(meals, 1),
        "trace": [f"plan_food → 餐饮合计 {round(meals, 1)} 元"],
    }


def merge_cost(state: TravelState) -> dict:
    """汇聚节点：把两条并行分支的费用与档位合成总价。"""
    req = state["request"]
    level = state.get("level", "standard")
    estimate = estimate_cost(req["city"], req["days"], level)
    tickets = state.get("attraction_cost", 0.0)
    meals = state.get("food_cost", 0.0)
    total = round(estimate["hotel"] * max(req["days"] - 1, 1) + tickets + meals, 1)
    return {
        "total_cost": total,
        "trace": [f"merge_cost → 档位 {level}，住宿 {estimate['hotel']}*{max(req['days'] - 1, 1)} 晚，合计 {total} 元"],
    }


def review_budget(state: TravelState) -> dict:
    """评估节点：只做判断与给意见，不做修改。"""
    req = state["request"]
    total = state.get("total_cost", 0.0)
    passed = total <= req["budget"]
    if passed:
        feedback = ""
    else:
        feedback = (
            f"总费用 {total} 元，超出预算 {round(total - req['budget'], 1)} 元；"
            "请换更省的档位并压缩高价项目，确保落在预算内。"
        )
    return {"feedback": feedback, "trace": [f"review_budget → {'达标' if passed else '超支'}（{total}/{req['budget']}）"]}


def route_budget(state: TravelState) -> str:
    """条件边：达标去审批，超支去优化；优化两轮仍超支就交给人工。"""
    if state.get("total_cost", 0.0) <= state["request"]["budget"]:
        return "await_approval"
    if state.get("round", 0) >= 2:
        return "await_approval"
    return "revise_plan"


def revise_plan(state: TravelState) -> dict:
    """优化器：按 feedback 降档重排，最多两轮。

    降档必须同步重算费用，否则 review_budget 拿到的还是旧总价，回边就成了空转。
    """
    req = state["request"]
    round_no = state.get("round", 0) + 1
    level = "frugal"
    prompt = (
        f"上一版行程总费用 {state.get('total_cost')} 元，预算只有 {req['budget']} 元。\n"
        f"评估意见：{state.get('feedback', '')}\n"
        f"请把{req['city']}{req['days']}天行程改成穷游版本：住青旅、吃小吃、多用免费景点，120 字以内。"
    )
    text = llm(max_tokens=240).invoke([SystemMessage(content=SYSTEM), HumanMessage(content=prompt)]).content

    estimate = estimate_cost(req["city"], req["days"], level)
    tickets = round(state.get("attraction_cost", 0.0) * 0.6, 1)   # 用免费景点替换掉贵的
    meals = state.get("food_cost", 0.0)
    total = round(estimate["hotel"] * max(req["days"] - 1, 1) + tickets + meals, 1)
    return {
        "level": level,
        "attractions": text.strip(),
        "round": round_no,
        "attraction_cost": tickets,
        "total_cost": total,
        "trace": [f"revise_plan → 第 {round_no} 轮优化，档位 {level}，重算合计 {total} 元"],
    }


def await_approval(state: TravelState) -> dict:
    """人机协同：暂停图，把决策权交给调用方。

    resume 传 bool 或 {"approved": bool, "note": str} 都接受。
    """
    req = state["request"]
    decision = interrupt(
        {
            "question": "是否批准这份行程？",
            "city": req["city"],
            "days": req["days"],
            "budget": req["budget"],
            "total_cost": state.get("total_cost"),
            "round": state.get("round", 0),
        }
    )
    if isinstance(decision, dict):
        approved = bool(decision.get("approved", True))
        note = str(decision.get("note", ""))
    else:
        approved = bool(decision)
        note = ""
    return {
        "approved": approved,
        "trace": [f"await_approval → {'批准' if approved else '否决'}{'（' + note + '）' if note else ''}"],
    }


def make_save_profile():
    """store 只能从 runtime 拿，用闭包把节点包成可直接 add_node 的函数。"""

    def save_profile_node(state: TravelState, runtime: Runtime[UserContext]) -> dict:
        req = state["request"]
        text = f"{req['city']} {req['days']} 天，偏好：{req['preference']}，预算 {req['budget']} 元"
        store = _store(runtime)
        if store is not None:
            import uuid

            store.put((_user_id(runtime), "profile"), str(uuid.uuid4()), {"text": text})
        return {"trace": [f"save_profile → 已写入画像：{text}"]}

    return save_profile_node


def finalize(state: TravelState) -> dict:
    """终稿：不再调模型，稳定拼接各节点产物。"""
    req = state["request"]
    verdict = "已批准" if state.get("approved") else "未获批准"
    plan = (
        f"# {req['city']} {req['days']} 天行程\n\n"
        f"- 预算：{req['budget']} 元 / 预估：{state.get('total_cost')} 元（{verdict}）\n"
        f"- 偏好：{req['preference']}\n"
        f"- 历史画像：{state.get('profile', '暂无')}\n\n"
        f"## 景点安排\n{state.get('attractions', '')}\n\n"
        f"## 美食安排\n{state.get('foods', '')}\n"
    )
    daily = state.get("daily_plans") or []
    if daily:
        plan += f"\n## 逐日细则\n{daily[-1]}\n"
    return {"final_plan": plan, "trace": ["finalize → 生成终稿"]}
