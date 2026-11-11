"""综合案例：AI 行程管家。

把 day13–day16 的能力串成一条真实链路：
    并行规划（景点 ∥ 美食） → 费用汇聚 → 预算评估
      ├ 超支 → 优化器回边（最多 2 轮）
      └ 达标 → 人工审批（interrupt）
    → 长期画像沉淀（store） → 终稿

运维入口：
    --stream         令牌级流式看模型输出
    --resume         恢复被中断的线程
    --fork-budget N  时间旅行：改预算后从 merge_cost 开新分支

用法：
    python case/travel_concierge.py --auto-approve
    python case/travel_concierge.py --city 成都 --days 3 --budget 1800 --auto-approve
    python case/travel_concierge.py --resume
    python case/travel_concierge.py --fork-budget 5000
"""
import argparse
import sqlite3
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.store.memory import InMemoryStore
from langgraph.types import Command

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.graphs import build_concierge_graph, draw  # noqa: E402
from lib.nodes import load_profile  # noqa: E402
from lib.state import TravelState, UserContext  # noqa: E402

DB_PATH = ROOT / "logs" / "travel_concierge.db"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI 行程管家")
    parser.add_argument("--city", default="杭州")
    parser.add_argument("--days", type=int, default=3)
    parser.add_argument("--budget", type=float, default=3000)
    parser.add_argument("--preference", default="喜欢自然风光，想少走路")
    parser.add_argument("--user", default="u1001")
    parser.add_argument("--thread", default="trip-demo-1")
    parser.add_argument("--auto-approve", action="store_true", help="免交互，自动批准")
    parser.add_argument("--stream", action="store_true", help="令牌级流式打印")
    parser.add_argument("--resume", action="store_true", help="恢复未完成的线程")
    parser.add_argument("--fork-budget", type=float, default=None, help="时间旅行改预算重算")
    return parser.parse_args()


def build_runtime():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    store = InMemoryStore()   # 进程内长记忆；换 Redis/Postgres 只需换这一个对象
    graph = build_concierge_graph(checkpointer=SqliteSaver(conn), store=store)
    return graph, conn, store


def run_stream(graph, payload, config, ctx) -> dict:
    """令牌级流式：只打印属于模型的 token，节点更新单独提示。

    坑：流式模式下 interrupt 不会出现在返回值里，而是作为一条 updates 块吐出
    （key 为 __interrupt__）；不把它捕回来，后续 resume 就无处可接。
    """
    interrupts = None
    for chunk in graph.stream(payload, config, context=ctx, stream_mode=["messages", "updates"], version="v2"):
        if isinstance(chunk, dict) and "type" in chunk:
            kind, data = chunk["type"], chunk["data"]
        else:
            kind, data = "messages", chunk
        if kind == "messages":
            msg, _meta = data
            text = getattr(msg, "content", "")
            if text:
                print(text, end="", flush=True)
        elif kind == "updates":
            if "__interrupt__" in data:
                interrupts = data["__interrupt__"]
    print()
    values = dict(graph.get_state(config).values)
    if interrupts:
        values["__interrupt__"] = interrupts
    return values


def print_result(result: dict) -> None:
    print("\n" + "=" * 60)
    print(result.get("final_plan", "（没有终稿）"))
    print("=" * 60)
    print("\n执行轨迹：")
    for i, line in enumerate(result.get("trace", []), 1):
        print(f"  {i:02d}. {line}")


def handle_interrupt(graph, result: dict, config, ctx, auto_approve: bool) -> dict:
    interrupt_info = result.get("__interrupt__")
    if not interrupt_info:
        return result
    payload = interrupt_info[0].value
    print("\n【需要人工审批】")
    print(f"  城市：{payload.get('city')} / {payload.get('days')} 天")
    print(f"  预算：{payload.get('budget')} 元 / 预估：{payload.get('total_cost')} 元 / 已优化 {payload.get('round', 0)} 轮")
    if auto_approve:
        approved, note = True, "auto-approve"
        print("  → 自动批准（--auto-approve）")
    else:
        try:
            answer = input("  是否批准？(y/n)：").strip().lower()
        except EOFError:
            print("  → 非交互环境，线程保持暂停；改用 --resume 继续")
            return result
        approved, note = answer.startswith("y"), "CLI 审批"
    return graph.invoke(Command(resume={"approved": approved, "note": note}), config, context=ctx)


def demo_fork(graph, config, ctx, new_budget: float) -> None:
    """时间旅行：找到 merge_cost 之前的快照，改预算后开新分支。"""
    print(f"\n【时间旅行】把预算改成 {new_budget} 元，从 merge_cost 之前开新分支")
    history = list(graph.get_state_history(config))
    target = next((s for s in history if s.next == ("merge_cost",)), None)
    if target is None:
        print("  未找到 merge_cost 之前的快照")
        return
    request = dict(target.values["request"])
    request["budget"] = new_budget
    fork_config = graph.update_state(target.config, values={"request": request}, as_node="load_profile")
    print(f"  原线程 checkpoint 不变，新分支 checkpoint={fork_config['configurable']['checkpoint_id'][:8]}…")
    out = graph.invoke(None, fork_config, context=ctx)
    # 恢复必须走线程头（只带 thread_id）：fork_config 里带着旧 checkpoint_id，
    # 用它 resume 会从那个旧点重跑，而不是接着刚停在的 interrupt。
    out = handle_interrupt(graph, out, config, ctx, auto_approve=True)
    print_result(out)


def demo_store_recall(store, user_id: str) -> None:
    """长期记忆验收：新 thread、只跑 load_profile，看能不能读到刚才沉淀的画像。

    这个迷你图不调模型，所以零成本；关键是 thread_id 换了但 user_id 没换。
    """
    mini = StateGraph(TravelState, context_schema=UserContext)
    mini.add_node("load_profile", load_profile)
    mini.add_edge(START, "load_profile")
    mini.add_edge("load_profile", END)
    graph = mini.compile(store=store)
    out = graph.invoke(
        {"request": {"city": "待定", "days": 1, "budget": 0, "preference": ""}},
        context=UserContext(user_id=user_id),
    )
    print(f"\n【长期记忆】换一个新 thread，用同一个 user_id={user_id} 回读画像：")
    print(f"  {out.get('profile')}")


def main() -> None:
    args = parse_args()
    graph, conn, store = build_runtime()
    print("主图结构：", draw(graph, "assets/case-concierge-graph.png"))

    config = {"configurable": {"thread_id": args.thread}}
    ctx = UserContext(user_id=args.user)

    snapshot = graph.get_state(config)
    if snapshot.next:
        print(f"\n线程 {args.thread} 有未完成任务，停在 {snapshot.next}")
        if not args.resume:
            print("加 --resume 继续执行")
            conn.close()
            return
        result = graph.invoke(Command(resume=True), config, context=ctx)
    elif args.resume:
        print(f"线程 {args.thread} 没有未完成任务")
        conn.close()
        return
    else:
        payload = {
            "request": {
                "city": args.city,
                "days": args.days,
                "budget": args.budget,
                "preference": args.preference,
            },
            "trace": [],
            "round": 0,
            "level": "standard",
            "daily_plans": [],
        }
        print(f"\n开始规划：{args.city} {args.days} 天，预算 {args.budget} 元")
        if args.stream:
            result = run_stream(graph, payload, config, ctx)
        else:
            result = graph.invoke(payload, config, context=ctx)

    result = handle_interrupt(graph, result, config, ctx, args.auto_approve)
    print_result(result)

    if args.fork_budget is not None:
        demo_fork(graph, config, ctx, args.fork_budget)

    demo_store_recall(store, args.user)

    print(f"\nSQLite 检查点文件：{DB_PATH}")
    conn.close()


if __name__ == "__main__":
    main()
