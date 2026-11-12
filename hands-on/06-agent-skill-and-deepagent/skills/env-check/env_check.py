"""运行时体检。

只回报告「端口通不通」和「环境变量在不在」，绝不打印变量值——
技能脚本会被模型读取输出，密钥一旦落到模型上下文就等于泄露。
"""
import argparse
import os
import platform
import socket
import sys


def port_open(host: str, port: int, timeout: float = 0.4) -> tuple[bool, str]:
    """返回 (是否监听, 错误说明)。探测本身失败与「端口未监听」是两件事，不能混。"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            return sock.connect_ex((host, port)) == 0, ""
    except OSError as exc:
        # Windows 上缺 SYSTEMROOT 会走到这里（WinError 10106），
        # 此时根本没探测过，不能当成未监听上报。
        return False, f"探测失败: {exc}"


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="检查 Python 运行时、指定端口占用与指定环境变量是否存在")
    parser.add_argument("--ports", type=str, default="", help="逗号分隔的端口号，如 2024,8080")
    parser.add_argument("--env", type=str, default="", help="逗号分隔的环境变量名，只检查存在性")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="探测端口的地址，默认本机回环")
    args = parser.parse_args()

    print(f"[env-check] Python: {platform.python_version()} ({platform.architecture()[0]})")
    print(f"[env-check] 系统: {platform.system()} {platform.release()}")

    ports = [p.strip() for p in args.ports.split(",") if p.strip()]
    if ports:
        for raw in ports:
            try:
                port = int(raw)
            except ValueError:
                print(f"[env-check] 端口非法，跳过: {raw}")
                continue
            opens, err = port_open(args.host, port)
            state = "已监听" if opens else "未监听"
            print(f"[env-check] 端口 {args.host}:{port} -> {state}{('（' + err + '）') if err else ''}")
    else:
        print("[env-check] 端口: 未指定")

    names = [n.strip() for n in args.env.split(",") if n.strip()]
    if names:
        for name in names:
            exists = bool(os.environ.get(name))
            print(f"[env-check] 环境变量 {name} -> {'已设置' if exists else '未设置'}")
    else:
        print("[env-check] 环境变量: 未指定")


if __name__ == "__main__":
    main()
