"""日志扫描。

按级别统计条数并给出样例行，正则只匹配独立的级别词，避免把正文里的
"error" 误判成一条 ERROR 记录。
"""
import argparse
import os
import re
import sys
from collections import Counter

LEVELS = ("DEBUG", "INFO", "WARN", "WARNING", "ERROR", "CRITICAL")
LEVEL_RE = re.compile(r"\b(" + "|".join(LEVELS) + r")\b")


def collect_files(path: str, pattern: str) -> list[str]:
    if os.path.isfile(path):
        return [path]
    files: list[str] = []
    for name in sorted(os.listdir(path)):
        if name.endswith(pattern):
            files.append(os.path.join(path, name))
    return files


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="统计日志文件里各等级的条数并列出指定等级的样例")
    parser.add_argument("--path", type=str, required=True, help="日志文件或日志目录")
    parser.add_argument("--level", type=str, default="ERROR", help="要列出样例的等级，默认 ERROR")
    parser.add_argument("--limit", type=int, default=5, help="样例最多列几条")
    parser.add_argument("--ext", type=str, default=".log", help="传目录时按此前缀筛选文件，默认 .log")
    args = parser.parse_args()

    if not os.path.exists(args.path):
        print(f"[log-scan] 路径不存在: {args.path}")
        raise SystemExit(2)

    files = collect_files(args.path, args.ext)
    if not files:
        print(f"[log-scan] 目录里没有 {args.ext} 文件: {args.path}")
        raise SystemExit(2)

    counter: Counter[str] = Counter()
    samples: list[str] = []
    target = args.level.upper()

    for fp in files:
        with open(fp, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                hit = LEVEL_RE.search(line)
                if not hit:
                    continue
                counter[hit.group(1)] += 1
                if hit.group(1) == target and len(samples) < args.limit:
                    samples.append(line.rstrip()[:200])

    print(f"[log-scan] 文件数: {len(files)}  路径: {os.path.abspath(args.path)}")
    print("[log-scan] 各等级条数: " + ", ".join(f"{k}={v}" for k, v in sorted(counter.items())) if counter else "[log-scan] 各等级条数: 0")
    print(f"[log-scan] {target} 样例 {len(samples)} 条:")
    for line in samples:
        print(f"  | {line}")
    print(f"[log-scan] {target} 总数: {counter.get(target, 0)}")


if __name__ == "__main__":
    main()
