"""阶段 3：DeepAgent 挂载技能目录，单技能调用。

验证三件事：
1. SkillsMiddleware 是否把技能元数据注入模型上下文
2. 模型会不会按 SKILL.md 的指引去执行脚本
3. 执行结果是不是真数据（能对上直接跑脚本的输出）

关键发现（本机 deepagents 0.7.35）：
- FilesystemBackend 只有读写文件的能力，没有执行命令的方法；要让技能里的脚本
  真的跑起来，必须用 LocalShellBackend。课件里用 FilesystemBackend + skills，
  模型只能读到 SKILL.md，脚本根本调不动。
- virtual_mode 两个值都不完美，实测记录见 logs/ 下两份对照日志：
  * True：read_file("/skills/...") 能读到；但 execute 的工作目录是真实 root_dir，
    模型若把 /skills/... 当 shell 路径去 cd 会连错 6 次（18 次调用那版）。
    在 SKILL.md 里写清「shell 工作目录就是项目根」并把 `../..` 改成 `..\..` 后，
    模型只发 1 次 read_file + 1 条 execute，降到 3 次调用。
  * False：read_file 直接报 Windows absolute paths are not supported，
    ls("/") 还把盘符根整棵目录树倒给模型（11 次调用那版）。
  结论：Windows 上留 virtual_mode=True，路径约定写进 SKILL.md。
"""
import re

from stages_common import ROOT, SKILLS, ask, build_agent, require_key

SKILL_NAMES = ("disk-usage", "log-scan", "env-check", "inspection-report")


def main() -> None:
    require_key()
    print(f"[s03] 项目根: {ROOT}")
    print(f"[s03] 技能目录: {SKILLS}")
    print(f"[s03] 技能: {[d.name for d in sorted(SKILLS.iterdir()) if d.is_dir()]}")

    agent = build_agent()

    a1, _c1, _m1 = ask(
        agent,
        "你现在能用哪些技能？只列技能名和一句话用途，不要调用任何工具。",
        "s03-discover",
    )

    a2, c2, _m2 = ask(
        agent,
        f"用磁盘技能查一下 {ROOT} 的占用情况，列出最大的前 3 个子目录，并说明磁盘剩余空间。",
        "s03-disk",
    )

    print("\n" + "-" * 68)
    checks = [
        ("技能元数据已注入（回答里提到至少两个技能名）",
         sum(name in a1 for name in SKILL_NAMES) >= 2),
        ("磁盘问答产生了工具调用", c2 > 0),
        ("回答里带脚本输出的真实数字",
         ".venv" in a2 and bool(re.search(r"\d+\.\d+\s*(MB|GB)", a2))),
    ]
    for title, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {title}")

    if all(ok for _t, ok in checks):
        print("[s03] OK：DeepAgent 能发现技能、按 SKILL.md 执行脚本并回报真实数据")
        return
    raise SystemExit(1)


if __name__ == "__main__":
    main()
