"""阶段脚本公用部分：构造 DeepAgent、打印工具调用轨迹。

单独抽出来是为了让 s03–s05 用完全一样的 Agent 配置，
对比结果时只差提问和技能目录，不掺别的变量。
"""
import os
import sys
from pathlib import Path

from deepagents import create_deep_agent
from deepagents.backends import LocalShellBackend
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"

SYSTEM_PROMPT = (
    "你是本机运维助手。回答任何涉及磁盘、日志、运行时状态的问题前，"
    "必须先找到对应技能，读取它的 SKILL.md，按里面的命令执行脚本，"
    "再用脚本返回的数据作答。禁止凭印象回答，禁止编造数字。"
)


def build_agent(skills_dir: Path | None = None):
    """按统一配置构造 Agent。

    backend 必须用 LocalShellBackend：FilesystemBackend 只能读写文件，
    技能里的脚本根本跑不起来。virtual_mode=True 是为了让 read_file 在
    Windows 上能用 /skills/... 这类虚拟路径读到 SKILL.md。

    inherit_env=True 是踩出来的：LocalShellBackend 默认不继承环境变量，
    子进程里没有 SYSTEMROOT，Windows 上 socket.socket() 会直接报
    OSError [WinError 10106]，env_check 的端口探测就全废了；
    同时技能也看不到 DEEPSEEK_API_KEY 之类的变量，会把「已设置」报成「未设置」。
    代价是 shell 子进程能读到本机所有环境变量，所以只在本机开发场景用，
    并且技能脚本一律不回显变量值。
    """
    model = ChatOpenAI(
        model=os.environ.get("MODEL_NAME", "deepseek-chat"),
        api_key=os.environ["DEEPSEEK_API_KEY"],
        base_url=os.environ.get("BASE_URL", "https://api.deepseek.com"),
        temperature=0,
    )
    backend = LocalShellBackend(
        root_dir=str(ROOT),
        virtual_mode=True,
        timeout=120,
        inherit_env=True,
    )
    return create_deep_agent(
        model=model,
        backend=backend,
        skills=[str(skills_dir or SKILLS)],
        checkpointer=MemorySaver(),
        system_prompt=SYSTEM_PROMPT,
    )


def show_trace(messages) -> int:
    """打印工具调用轨迹，返回本轮工具调用次数。"""
    calls = 0
    for msg in messages:
        role = getattr(msg, "type", msg.__class__.__name__)
        for call in getattr(msg, "tool_calls", None) or []:
            calls += 1
            args = str(call.get("args", {}))[:160]
            print(f"    -> 调用 {call.get('name')} 参数 {args}")
        if role == "tool":
            content = str(getattr(msg, "content", ""))[:200].replace("\n", " ")
            print(f"    <- 工具返回 {content}")
    return calls


def ask(agent, question: str, thread: str) -> tuple[str, int, list]:
    """一轮提问，返回 (回答, 工具调用次数, 消息列表)。"""
    print(f"\n>>> 提问：{question}")
    result = agent.invoke(
        {"messages": [{"role": "user", "content": question}]},
        config={"configurable": {"thread_id": thread}},
    )
    messages = result["messages"]
    calls = show_trace(messages)
    answer = str(messages[-1].content)
    print(f"\n<<< 回答：\n{answer}")
    print(f"    （本轮工具调用 {calls} 次）")
    return answer, calls, messages


def require_key() -> None:
    if not os.environ.get("DEEPSEEK_API_KEY"):
        print("环境变量 DEEPSEEK_API_KEY 未设置，无法调用模型")
        raise SystemExit(2)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
