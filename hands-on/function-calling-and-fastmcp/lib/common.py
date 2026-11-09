"""公共工具：控制台编码、日志（同时写标准输出与 logs/<stage>.log）。"""
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # hands-on/function-calling-and-fastmcp
LOG_DIR = ROOT / "logs"


def setup_logging(stage: str) -> logging.Logger:
    """每个阶段一个 logger，日志落 logs/<stage>.log，作为验证证据入库。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(stage)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")
    fh = logging.FileHandler(LOG_DIR / f"{stage}.log", encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    return logger


def banner(logger: logging.Logger, title: str) -> None:
    logger.info("=" * 72)
    logger.info(title)
    logger.info("=" * 72)
