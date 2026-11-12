"""磁盘占用速查。

只做确定性的事：算目录大小、读磁盘余量，不做任何判断。
"""
import argparse
import os
import shutil
import sys


def human(size: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def dir_size(path: str) -> int:
    """递归求目录总字节数，遇权限错误直接跳过，不中断统计。"""
    total = 0
    for root, _dirs, files in os.walk(path, onerror=lambda _e: None):
        for name in files:
            fp = os.path.join(root, name)
            try:
                total += os.path.getsize(fp)
            except OSError:
                continue
    return total


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="统计指定目录下各子目录占用与所在盘余量")
    parser.add_argument("--path", type=str, required=True, help="要统计的目录绝对路径")
    parser.add_argument("--top", type=int, default=8, help="列出占用最大的前 N 个子目录")
    args = parser.parse_args()

    target = os.path.abspath(args.path)
    if not os.path.isdir(target):
        print(f"[disk-usage] 目录不存在: {target}")
        raise SystemExit(2)

    usage = shutil.disk_usage(target)
    used_pct = usage.used / usage.total * 100 if usage.total else 0
    print(f"[disk-usage] 目 录: {target}")
    print(f"[disk-usage] 所 在 盘: 总 {human(usage.total)} / 已用 {human(usage.used)} / 剩余 {human(usage.free)} ({used_pct:.1f}% 已用)")

    rows = []
    for name in os.listdir(target):
        sub = os.path.join(target, name)
        if os.path.isdir(sub) and not os.path.islink(sub):
            rows.append((name, dir_size(sub)))
    rows.sort(key=lambda item: item[1], reverse=True)

    print(f"[disk-usage] 子目录占用 Top {min(args.top, len(rows))}:")
    for idx, (name, size) in enumerate(rows[: args.top], 1):
        print(f"  {idx}. {name:<28} {human(size)}")


if __name__ == "__main__":
    main()
