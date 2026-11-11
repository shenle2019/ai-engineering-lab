"""s10 服务化：图通过 langgraph.json 暴露成 HTTP API，客户端不碰 Python 对象。

前置（另开一个终端，在 05 目录下跑）：
    langgraph dev --port 2024 --no-browser
Windows 上要带 PYTHONUTF8=1，否则 langgraph_api 读 OpenAPI 文件会按 GBK 解码报错。

本脚本只做客户端，验证四件事：
1. GET /ok 服务就绪
2. GET /assistants 能发现 concierge 图
3. POST /threads + /runs/wait 跑起来，并在 await_approval 处被 interrupt
4. 同一个 thread 用 command.resume 恢复，跑到 finalize
"""
import json
import sys
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:2024"


def call(method: str, path: str, payload: dict | None = None, timeout: int = 300) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body) if body else {}


def wait_ready(timeout: int = 60) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            ok = call("GET", "/ok", timeout=5)
            print(f"[1] GET /ok → {ok}")
            return
        except (urllib.error.URLError, TimeoutError):
            time.sleep(1)
    raise SystemExit("服务没起来：先在 05 目录执行 langgraph dev --port 2024 --no-browser")


def find_assistant(graph_id: str = "concierge") -> str:
    # 注意：助手列表是 POST /assistants/search，GET /assistants 会回 405
    raw = call("POST", "/assistants/search", {"limit": 10})
    items = raw if isinstance(raw, list) else raw.get("assistants", [])
    for item in items:
        if item.get("graph_id") == graph_id:
            print(f"[2] POST /assistants/search → graph_id={graph_id} assistant_id={item['assistant_id']}")
            return item["assistant_id"]
    raise SystemExit(f"没有找到 graph_id={graph_id}，检查 langgraph.json 的 graphs 配置")


def main() -> None:
    wait_ready()
    assistant_id = find_assistant()

    thread = call("POST", "/threads", {})
    thread_id = thread["thread_id"]
    print(f"[3] POST /threads → thread_id={thread_id}")

    payload = {
        "assistant_id": assistant_id,
        "context": {"user_id": "u1001"},   # 服务端的 context 就是图的 context_schema
        "input": {
            "request": {
                "city": "成都",
                "days": 3,
                "budget": 1800,
                "preference": "爱吃辣，想看不那么挤的景点",
            },
            "trace": [],
            "round": 0,
            "level": "standard",
            "daily_plans": [],
        },
    }
    result = call("POST", f"/threads/{thread_id}/runs/wait", payload)
    interrupts = result.get("__interrupt__") or []
    print(f"    POST /runs/wait → 收到 {len(interrupts)} 个 interrupt")
    if interrupts:
        value = interrupts[0].get("value", interrupts[0])
        print(f"    审批内容：{json.dumps(value, ensure_ascii=False)}")
    print(f"    轨迹：{' | '.join(result.get('trace', []))}")
    print(f"    final_plan 是否已生成：{bool(result.get('final_plan'))}")

    print("[4] POST /runs/wait + command.resume")
    resumed = call(
        "POST",
        f"/threads/{thread_id}/runs/wait",
        {
            "assistant_id": assistant_id,
            "context": {"user_id": "u1001"},
            "command": {"resume": {"approved": True, "note": "API 审批"}},
        },
    )
    print(f"    轨迹：{' | '.join(resumed.get('trace', []))}")
    plan = resumed.get("final_plan") or ""
    print("    终稿前 3 行：")
    for line in plan.splitlines()[:3]:
        print(f"      {line}")

    assert plan, "恢复后没拿到 final_plan"
    print("\nS10 OK：服务化链路 /ok → /assistants → /threads → /runs/wait → resume 全部走通")


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
