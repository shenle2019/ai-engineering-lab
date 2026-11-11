"""langgraph dev / SDK 的服务入口：导出一个编译好的 graph。

langgraph.json 里通过 `./lib/service.py:graph` 指向本文件。

两个坑：
1. langgraph dev 按「单文件模块」加载入口（module=None），写 `from .graphs import ...`
   会报 `attempted relative import with no known parent package`——这里把项目根加入
   sys.path，改成绝对导入 `lib.graphs`，包内部的相对导入照旧能用。
2. 服务端会自己注入 checkpointer 与 store，图里再传一份会被当成配置冲突；
   所以这里编译时不带持久化，本地 CLI 跑才自己传 SqliteSaver。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.graphs import build_concierge_graph  # noqa: E402

graph = build_concierge_graph()
