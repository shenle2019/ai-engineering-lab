"""PC 文件助手 MCP server（FastMCP）。

对照课件 day02 的 AI PC 助手，这里只复刻"文件整理"两个工具，不做卸载软件：
卸载属于高破坏性操作，学习场景下没有安全的验证方式，刻意省略（README 有说明）。

安全边界：
- 拒绝 Windows 系统目录与 Program Files（防止误整理）
- 只处理传入目录的顶层文件，不递归、不删除、同名跳过
- 整理只做"移动到子文件夹"，可手工还原

启动：python servers/pc_helper_server.py            # stdio
"""
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastmcp import FastMCP  # noqa: E402

mcp = FastMCP(
    name="PC文件助手",
    instructions="提供本机文件整理能力：列出目录文件信息、按扩展名把文件归类到子文件夹。只处理普通文件目录。",
)

DENY_PREFIXES = (
    "c:\\windows",
    "c:\\program files",
    "c:\\program files (x86)",
    "c:\\programdata",
)


def _check_dir(path: str) -> Path:
    target = Path(path).expanduser().resolve()
    if any(str(target).lower().startswith(p) for p in DENY_PREFIXES):
        raise PermissionError(f"拒绝操作系统目录：{target}（安全边界）")
    if not target.exists():
        raise FileNotFoundError(f"路径不存在：{target}")
    if not target.is_dir():
        raise NotADirectoryError(f"不是目录：{target}")
    return target


def _readable_size(num: int) -> str:
    if num < 1024:
        return f"{num} B"
    if num < 1024 ** 2:
        return f"{num / 1024:.2f} KB"
    if num < 1024 ** 3:
        return f"{num / 1024 ** 2:.2f} MB"
    return f"{num / 1024 ** 3:.2f} GB"


@mcp.tool(name="list_files", description="列出指定目录下的文件名、类型和大小（只看顶层，不含子目录）")
def list_files(path: str) -> str:
    try:
        target = _check_dir(path)
    except (PermissionError, FileNotFoundError, NotADirectoryError) as exc:
        return f"错误：{exc}"

    files = sorted(f for f in target.iterdir() if f.is_file())
    if not files:
        return f"目录 {target} 下没有文件。"
    lines = [f"目录：{target}", f"{'文件名':<40}{'类型':<10}{'大小':<12}字节"]
    for f in files:
        lines.append(f"{f.name:<40}{(f.suffix[1:] or '无'):<10}{_readable_size(f.stat().st_size):<12}{f.stat().st_size}")
    return "\n".join(lines)


@mcp.tool(name="organize_by_type", description="按扩展名把目录下的文件移动到 YYYYMMDD_扩展名 子文件夹，同名文件跳过不覆盖")
def organize_by_type(path: str) -> str:
    try:
        target = _check_dir(path)
    except (PermissionError, FileNotFoundError, NotADirectoryError) as exc:
        return f"错误：{exc}"

    files = [f for f in target.iterdir() if f.is_file()]
    if not files:
        return f"目录 {target} 下没有文件需要整理。"

    groups: dict[str, list[Path]] = {}
    for f in files:
        groups.setdefault(f.suffix.lower()[1:] or "no_ext", []).append(f)

    today = datetime.now().strftime("%Y%m%d")
    moved, skipped = 0, 0
    detail = []
    for ext, items in sorted(groups.items()):
        folder = target / f"{today}_{ext}"
        folder.mkdir(exist_ok=True)
        for src in items:
            dest = folder / src.name
            if dest.exists():
                skipped += 1
                detail.append(f"跳过（已存在）：{src.name}")
                continue
            shutil.move(str(src), str(dest))
            moved += 1
            detail.append(f"移动：{src.name} -> {folder.name}/")
    return "\n".join([f"整理完成：移动 {moved} 个，跳过 {skipped} 个，共 {len(files)} 个文件。", *detail])


if __name__ == "__main__":
    mcp.run()
