"""阶段 05：AI PC 助手（文件整理）在沙箱目录里验证。

对照课件 day02 的 AI PC 助手，验证点：
1. list_files 能列出文件名/类型/大小
2. organize_by_type 按扩展名归入 YYYYMMDD_ext 子文件夹
3. 再整理一次全部跳过 —— 说明工具幂等，不会覆盖已有文件
4. 安全边界：系统目录被拒绝、不存在路径返回错误而不是抛栈

沙箱建在系统临时目录，验证完即删，不在仓库里留垃圾文件。
"""
import asyncio
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastmcp import Client  # noqa: E402

from lib.common import setup_logging, banner  # noqa: E402

STAGE = "05_pc_helper"
SERVER = ROOT / "servers" / "pc_helper_server.py"

SAMPLE_FILES = {
    "报告.docx": b"fake docx",
    "预算表.xlsx": b"fake xlsx",
    "截图.png": b"fake png",
    "笔记.md": b"# note",
    "README": b"no ext",
    "备份.docx": b"fake docx 2",
}


def text_of(result) -> str:
    """FastMCP 的工具返回值可能是 str，也可能是内容块列表，统一取文本。"""
    content = getattr(result, "content", None)
    if content is None:
        return str(result)
    return "\n".join(getattr(c, "text", str(c)) for c in content)


def build_sandbox() -> Path:
    sandbox = Path(tempfile.mkdtemp(prefix="pc_helper_"))
    for name, data in SAMPLE_FILES.items():
        (sandbox / name).write_bytes(data)
    return sandbox


async def demo(log, sandbox: Path) -> bool:
    checks = {}

    client = Client(str(SERVER))
    async with client:
        log.info("---- 1. 列出目录文件")
        out = text_of(await client.call_tool("list_files", {"path": str(sandbox)}))
        log.info("%s", out)
        checks["list_files"] = all(name in out for name in SAMPLE_FILES)

        log.info("")
        log.info("---- 2. 按扩展名整理")
        out = text_of(await client.call_tool("organize_by_type", {"path": str(sandbox)}))
        log.info("%s", out)
        checks["organize"] = "移动 6 个" in out

        folders = sorted(p.name for p in sandbox.iterdir() if p.is_dir())
        log.info("生成子文件夹：%s", folders)
        checks["folders"] = len(folders) == 5  # docx / xlsx / png / md / no_ext
        for folder in sorted(sandbox.iterdir()):
            if folder.is_dir():
                log.info("  %s/ -> %s", folder.name, [f.name for f in folder.iterdir()])

        log.info("")
        log.info("---- 3. 再整理一次（幂等性 / 不覆盖）")
        out = text_of(await client.call_tool("organize_by_type", {"path": str(sandbox)}))
        log.info("%s", out)
        checks["idempotent"] = "没有文件需要整理" in out or "跳过" in out

        log.info("")
        log.info("---- 4. 安全边界：系统目录")
        out = text_of(await client.call_tool("list_files", {"path": "C:\\Windows"}))
        log.info("%s", out)
        checks["deny_system"] = out.startswith("错误") and "安全边界" in out

        log.info("")
        log.info("---- 5. 不存在路径")
        out = text_of(await client.call_tool("list_files", {"path": str(sandbox / "nope")}))
        log.info("%s", out)
        checks["bad_path"] = out.startswith("错误")

    for name, ok in checks.items():
        log.info("检查项 %-12s %s", name, "通过" if ok else "失败")
    return all(checks.values())


def main() -> int:
    log = setup_logging(STAGE)
    banner(log, "阶段 05 AI PC 助手：文件整理")
    sandbox = build_sandbox()
    log.info("沙箱目录：%s", sandbox)
    try:
        ok = asyncio.run(demo(log, sandbox))
    finally:
        import shutil

        shutil.rmtree(sandbox, ignore_errors=True)
        log.info("沙箱已清理：%s", not sandbox.exists())
    log.info("")
    log.info("阶段 05 %s", "全部通过" if ok else "存在失败项")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
