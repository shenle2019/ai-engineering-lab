# Hands-on

实操练习与案例复刻记录。

## 已收录

| 目录 | 内容 | 验证状态 |
| --- | --- | --- |
| [01-linux-docker-compose-deploy](01-linux-docker-compose-deploy) | 预习1–3：Linux 基础 → redis/nginx 单容器 → Dockerfile 构建 Flask 计数应用 → Compose 三服务编排 → 镜像 save/load 迁移 | 已在本机 WSL2 + Docker 29.1.3 跑通，5 个阶段日志齐全 |
| [02-function-calling-and-fastmcp](02-function-calling-and-fastmcp) | day01–day02：手工 Function Calling 七步 → 东方财富行情工具 → FastMCP 发布 MCP server（两种传输、三组件、中间件）→ PC 文件助手 → LLM 经 MCP Host 调工具 | 已在本机 Windows + Python 3.11 + fastmcp 2.14.7 + DeepSeek 真跑，7 个阶段日志齐全 |
| [03-langchain-agent-engineering](03-langchain-agent-engineering) | day03–day07 串成一条电商客服案例：Agents/Models/Messages → 流式与结构化输出 → 工具与短期记忆与护栏 → MCP 与 HITL → 中间件与长期记忆与上下文工程 → 多智能体 → 综合案例 | 已在本机 Windows + Python 3.11.9 + LangChain 1.4.9 + DeepSeek 真跑，7 个阶段 + 1 个案例日志齐全 |

## 约定

- 每个实操一个子目录，目录名按关键知识点命名（如 `03-langchain-agent-engineering`），用 `01-`、`02-`… 数字前缀表示学习顺序，不使用课次编号
- 子目录内放可运行代码与实操记录文档，记录关键步骤、踩坑与结论
- 只收录验证过能跑通的内容
