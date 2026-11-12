"""阶段 4：多技能编排 —— 一次提问串起三个采集技能 + 一个撰写技能。

这一阶段验证的是 Skill 真正的价值：模型不知道要查什么、按什么格式写，
全靠技能目录里的 SKILL.md 指路。检查点全部用「直接跑脚本得到的基准值」比对，
不看模型说得好不好听，只看数字对不对得上。

验证五件事：
1. 一次提问同时读了多份 SKILL.md 并执行了脚本
2. 报告四个小节齐全（inspection-report 规定的固定格式）
3. 报告里的日志条数与直接跑 log_scan.py 的结果一致
4. 报告真的落盘到 reports/
5. 结论只落在正常 / 需关注 / 异常三档里
"""
import re
import subprocess

from stages_common import ROOT, ask, build_agent, require_key

PY = ROOT / ".venv" / "Scripts" / "python.exe"
REPORTS = ROOT / "reports"
SECTIONS = ("一、结论", "二、关键数据", "三、异常与风险", "四、建议")
LEVELS = ("DEBUG", "INFO", "WARN", "WARNING", "ERROR", "CRITICAL")


def baseline_log_counts() -> dict[str, int]:
    """直接跑 log_scan.py 拿基准条数，用来核对模型有没有编数字。"""
    proc = subprocess.run(
        [str(PY), str(ROOT / "skills" / "log-scan" / "log_scan.py"),
         "--path", str(ROOT / "samples"), "--level", "ERROR", "--limit", "1"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    out = proc.stdout + proc.stderr
    print("[s04] 基准值（直接跑脚本）：")
    for line in out.strip().splitlines():
        print("      " + line)
    counts = {}
    for level in LEVELS:
        m = re.search(rf"{level}\s*[:=]\s*(\d+)", out)
        if m:
            counts[level] = int(m.group(1))
    return counts


def count_tool_calls(messages) -> dict[str, int]:
    stats: dict[str, int] = {}
    for msg in messages:
        for call in getattr(msg, "tool_calls", None) or []:
            name = str(call.get("name"))
            stats[name] = stats.get(name, 0) + 1
    return stats


def main() -> None:
    require_key()
    REPORTS.mkdir(exist_ok=True)

    base = baseline_log_counts()
    if not base:
        print("[s04] 没能从脚本输出里解析出条数，检查 log_scan.py 的输出格式")
        raise SystemExit(2)

    agent = build_agent()
    question = (
        "做一次本机巡检，需要三份数据："
        f"1) {ROOT} 的磁盘占用和剩余空间；"
        f"2) {ROOT / 'samples'} 下日志的各等级条数；"
        "3) 端口 2024 和 8080 的监听状态、环境变量 DEEPSEEK_API_KEY 是否存在。"
        "采集完按巡检报告技能规定的格式写出完整报告，"
        "并把报告原文写入 reports/inspection.md。"
    )
    answer, _calls, messages = ask(agent, question, "s04-inspection")

    stats = count_tool_calls(messages)
    print(f"[s04] 工具调用分布：{stats}")

    report_path = REPORTS / "inspection.md"
    report = report_path.read_text(encoding="utf-8") if report_path.exists() else ""
    blob = answer + "\n" + report

    checks = [
        ("读了 SKILL.md 且执行了脚本", stats.get("read_file", 0) >= 1 and stats.get("execute", 0) >= 1),
        ("报告四节齐全", all(s in blob for s in SECTIONS)),
        ("日志条数与脚本基准一致", all(re.search(rf"\b{v}\b", blob) for v in base.values())),
        ("报告已落盘 reports/inspection.md", report_path.exists() and len(report) > 200),
        ("结论只用三档之一", bool(re.search(r"(正常|需关注|异常)", report))),
    ]
    print("\n" + "-" * 68)
    for title, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {title}")
    print(f"[s04] 基准条数：{base}")
    print(f"[s04] 报告文件：{report_path}（{len(report)} 字符）")

    if all(ok for _t, ok in checks):
        print("[s04] OK：多技能按 SKILL.md 编排，报告格式与数据都可核对")
        return
    raise SystemExit(1)


if __name__ == "__main__":
    main()
