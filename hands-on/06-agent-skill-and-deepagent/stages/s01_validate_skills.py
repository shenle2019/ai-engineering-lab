"""阶段 1：技能目录合规性校验。

把课件里「必须遵守的规范」变成可执行的检查：front matter 能不能解析、
name 是否等于目录名、命名是不是 kebab-case、description 够不够具体、
正文提到的脚本是否真的存在。跑一遍就知道这套技能能不能交给 Agent。
"""
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / "skills"

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
SCRIPT_REF_RE = re.compile(r"([A-Za-z0-9_\-]+\.py)")


def split_front_matter(text: str) -> tuple[dict | None, str, str]:
    """把 SKILL.md 拆成 meta 与正文，返回 (meta, body, 错误说明)。"""
    if not text.startswith("---"):
        return None, text, "文件没有以 --- 开头，缺少 YAML front matter"
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None, text, "front matter 没有闭合的 ---"
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError as exc:
        return None, text, f"YAML 解析失败: {exc}"
    if not isinstance(meta, dict):
        return None, text, "front matter 不是键值对"
    return meta, parts[2], ""


def check_one(skill_dir: Path) -> tuple[str, list[str]]:
    problems: list[str] = []
    md = skill_dir / "SKILL.md"
    if not md.is_file():
        return skill_dir.name, ["缺少 SKILL.md"]

    meta, body, err = split_front_matter(md.read_text(encoding="utf-8"))
    if meta is None:
        return skill_dir.name, [err]

    name = str(meta.get("name", "")).strip()
    desc = str(meta.get("description", "")).strip()

    if not name:
        problems.append("name 缺失")
    elif name != skill_dir.name:
        problems.append(f"name({name}) 与目录名({skill_dir.name}) 不一致")
    elif not NAME_RE.match(name):
        problems.append("name 不符合 kebab-case：只允许小写字母、数字、连字符")

    if not desc:
        problems.append("description 缺失")
    elif len(desc) < 15:
        problems.append("description 太短，写不出触发场景，命中率会很低")

    if len(body.strip()) < 80:
        problems.append("正文过短，缺少可执行的步骤说明")

    for script in sorted(set(SCRIPT_REF_RE.findall(body))):
        if not (skill_dir / script).is_file():
            problems.append(f"正文引用了脚本 {script}，但目录里没有这个文件")

    return skill_dir.name, problems


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    if not SKILLS_DIR.is_dir():
        print(f"[s01] 找不到技能目录: {SKILLS_DIR}")
        raise SystemExit(2)

    dirs = sorted(d for d in SKILLS_DIR.iterdir() if d.is_dir())
    if not dirs:
        print(f"[s01] {SKILLS_DIR} 下没有任何技能目录")
        raise SystemExit(2)

    print(f"[s01] 技能根目录: {SKILLS_DIR}")
    print(f"[s01] 待校验技能: {len(dirs)} 个")
    print("-" * 68)

    failed = 0
    for idx, d in enumerate(dirs, 1):
        name, problems = check_one(d)
        tag = "PASS" if not problems else "FAIL"
        print(f"[{idx}/{len(dirs)}] {name:<20} {tag}")
        for p in problems:
            print(f"        - {p}")
        failed += 1 if problems else 0

    print("-" * 68)
    print(f"[s01] 汇总：{len(dirs)} 个技能，通过 {len(dirs) - failed}，失败 {failed}")
    if failed:
        raise SystemExit(1)
    print("[s01] OK：所有技能目录符合 SKILL.md 规范")


if __name__ == "__main__":
    main()
