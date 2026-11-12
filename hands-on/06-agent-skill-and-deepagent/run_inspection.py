"""综合案例入口：一条命令跑完「技能自检 → Agent 巡检 → 报告落盘」。

用法：
    .\\.venv\\Scripts\\python.exe run_inspection.py
    .\\.venv\\Scripts\\python.exe run_inspection.py --target "E:\\some\\dir" --skip-validate

流程：
1. 先跑 s01 的合规校验，技能不合格就直接停（不合格的技能交给模型只会更糟）
2. 构造挂载了 skills/ 的 DeepAgent，让它按 SKILL.md 自己取三项数据
3. 校验报告四节齐全、结论落在三档内，报告路径打印出来

这一步刻意不在代码里写死「先跑 disk-usage 再跑 log-scan」：编排权交给模型，
代码只负责闸门和验收。技能写得好不好，从工具调用轨迹里一眼能看出来。
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "stages"))

from stages_common import ROOT as PROJ_ROOT, ask, build_agent, require_key  # noqa: E402

SECTIONS = ("一、结论", "二、关键数据", "三、异常与风险", "四、建议")
REPORT = ROOT / "reports" / "inspection.md"


def validate_skills() -> bool:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "stages" / "s01_validate_skills.py")],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    tail = [ln for ln in (proc.stdout or "").strip().splitlines() if ln.strip()]
    print(tail[-1] if tail else "[case] s01 无输出")
    return proc.returncode == 0


def main() -> None:
    parser = argparse.ArgumentParser(description="本机巡检综合案例：技能自检 + DeepAgent 采集 + 报告落盘")
    parser.add_argument("--target", default=str(PROJ_ROOT), help="要巡检的目录，默认项目根")
    parser.add_argument("--log-dir", default=str(PROJ_ROOT / "samples"), help="要扫描的日志目录")
    parser.add_argument("--ports", default="2024,8080", help="要探测的端口，逗号分隔")
    parser.add_argument("--env-var", default="DEEPSEEK_API_KEY", help="要确认是否存在的环境变量名")
    parser.add_argument("--skip-validate", action="store_true", help="跳过 s01 技能校验")
    args = parser.parse_args()

    require_key()
    if not args.skip_validate and not validate_skills():
        print("[case] 技能校验未通过，先修 SKILL.md 再跑巡检")
        raise SystemExit(1)

    agent = build_agent()
    question = (
        "做一次本机巡检，需要三份数据："
        f"1) {args.target} 的磁盘占用和剩余空间；"
        f"2) {args.log_dir} 下日志的各等级条数；"
        f"3) 端口 {args.ports} 的监听状态、环境变量 {args.env_var} 是否存在。"
        "采集完按巡检报告技能规定的格式写出完整报告，"
        f"并把报告原文写入 {REPORT}。"
    )
    answer, calls, _messages = ask(agent, question, "case-inspection")

    if not REPORT.exists():
        print(f"[case] 报告没有落盘：{REPORT}")
        raise SystemExit(1)
    report = REPORT.read_text(encoding="utf-8")
    blob = answer + "\n" + report

    missing = [s for s in SECTIONS if s not in blob]
    verdict = re.search(r"(正常|需关注|异常)", report)
    print("\n" + "=" * 68)
    print(f"[case] 工具调用 {calls} 次")
    print(f"[case] 报告：{REPORT}（{len(report)} 字符）")
    print(f"[case] 四节齐全：{'是' if not missing else '缺 ' + '、'.join(missing)}")
    print(f"[case] 结论：{verdict.group(1) if verdict else '未给出'}")
    if missing or not verdict:
        raise SystemExit(1)
    print("[case] OK：一条命令完成技能自检与巡检报告产出")


if __name__ == "__main__":
    main()
