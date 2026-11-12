"""阶段 2：绕过 Agent，直接跑三个脚本技能。

先证明脚本层是可靠的：正常参数下输出可解析，缺参数、路径不存在时
必须非零退出并给出明确错误。脚本不可靠，上面的 Agent 再聪明也没用。
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / ".venv" / "Scripts" / "python.exe"
SKILLS = ROOT / "skills"


def run(title: str, args: list[str], expect_ok: bool, must_contain: list[str] | None = None) -> bool:
    cmd = [str(PY)] + args
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (proc.stdout or "") + (proc.stderr or "")
    ok = (proc.returncode == 0) == expect_ok
    if must_contain:
        missing = [k for k in must_contain if k not in out]
        ok = ok and not missing
    else:
        missing = []

    print(f"\n=== {title} ===")
    print("命令:", " ".join(args))
    print("退出码:", proc.returncode, "| 预期:", "成功" if expect_ok else "失败")
    for line in out.strip().splitlines()[:12]:
        print("  " + line)
    if len(out.strip().splitlines()) > 12:
        print(f"  ... 其余 {len(out.strip().splitlines()) - 12} 行省略")
    if missing:
        print("  缺少预期关键词:", missing)
    print("结论:", "PASS" if ok else "FAIL")
    return ok


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    if not PY.is_file():
        print(f"[s02] 找不到虚拟环境解释器: {PY}")
        raise SystemExit(2)

    sample_log = ROOT / "samples" / "app.log"
    results = [
        run(
            "磁盘技能：正常调用",
            [str(SKILLS / "disk-usage" / "disk_usage.py"), "--path", str(ROOT), "--top", "5"],
            True,
            ["[disk-usage]", "子目录占用 Top"],
        ),
        run(
            "磁盘技能：路径不存在",
            [str(SKILLS / "disk-usage" / "disk_usage.py"), "--path", str(ROOT / "no-such-dir")],
            False,
            ["目录不存在"],
        ),
        run(
            "日志技能：扫样例日志",
            [str(SKILLS / "log-scan" / "log_scan.py"), "--path", str(sample_log), "--level", "ERROR"],
            True,
            ["[log-scan]", "ERROR 总数: 3"],
        ),
        run(
            "日志技能：缺必填参数",
            [str(SKILLS / "log-scan" / "log_scan.py")],
            False,
            ["required", "--path"],
        ),
        run(
            "运行时技能：端口与变量",
            [str(SKILLS / "env-check" / "env_check.py"), "--ports", "2024,65000", "--env", "DEEPSEEK_API_KEY,NO_SUCH_VAR"],
            True,
            ["[env-check]", "DEEPSEEK_API_KEY -> 已设置", "NO_SUCH_VAR -> 未设置"],
        ),
    ]

    passed = sum(1 for r in results if r)
    print("\n" + "-" * 68)
    print(f"[s02] 汇总：{len(results)} 个检查，通过 {passed}，失败 {len(results) - passed}")
    if passed != len(results):
        raise SystemExit(1)
    print("[s02] OK：三个脚本技能在正常与异常路径上都符合预期")


if __name__ == "__main__":
    main()
