# AI Engineering Lab

Python 山顶会三期的学习仓库：**课件笔记** + **实操复刻记录** 两条线并行。

- `notes/`：从课件提炼的知识笔记，按知识点命名，只记录理解，不复刻代码
- `hands-on/`：按课件自己重写并跑通的实操，每个实操一个子目录，附带源码、脚本和运行日志

## 课程地图与进度

| 阶段 | 课次 | 主题 | 笔记 | 实操 |
| --- | --- | --- | --- | --- |
| 环境基础 | 预习1 | Linux 入门操作（命令、权限、软硬链接、vim、服务、进程） | Linux与Docker容器化基础.md | linux-docker-compose-deploy |
| 环境基础 | 预习2 | Docker 从入门到精通（镜像、容器、Dockerfile、迁移备份） | 同上 | 同上 |
| 环境基础 | 预习3 | Docker Compose 详解（服务、项目、多容器编排） | 同上 | 同上 |
| 工具调用 | day01 | Function Calling 之 AI 股票小助手和 MCP | FunctionCalling与FastMCP-MCP协议与服务端开发.md | 待做 |
| 工具调用 | day02 | FastMCP 从入门到精通 | 同上 | 待做 |
| LangChain | day03 | LangChain v1.2.9 核心组件之 Agents 和 Models | 待做 | 待做 |
| LangChain | day04 | LangChain 核心之 Models 模型和 Messages 消息 | 待做 | 待做 |
| LangChain | day05 | LangChain 结构化输出和流式输出 | 待做 | 待做 |
| LangChain | day06 | LangChain 高级组件之工具 / 短期记忆 / 护栏 / MCP / 人机交互 | 待做 | 待做 |
| LangChain | day07 | LangChain 高级组件之中间件 / 运行时 / 上下文工程 / 长期记忆 | 待做 | 待做 |
| 项目二次开发 | day08 | GitHub 项目二次开发（起步） | 待做 | 待做 |
| 项目二次开发 | day09 | GitHub 项目二次开发 + Nuxt 框架 | 待做 | 待做 |
| 项目二次开发 | day10 | GitHub 项目二次开发 + 源码分析 | 待做 | 待做 |
| 项目二次开发 | day11 | 源码分析与二次开发（含 AGENTS.md 开发准则） | 待做 | 待做 |
| 项目二次开发 | day12 | AI 功能二次开发与项目部署 | 待做 | 待做 |
| LangGraph | day13 | LangGraph 之智能导游案例与本地服务 | 待做 | 待做 |
| LangGraph | day14 | LangGraph 核心架构模式和子图 | 待做 | 待做 |
| LangGraph | day15 | LangGraph 之子图 / 记忆 / 中断 / 持久化 | 待做 | 待做 |
| LangGraph | day16 | LangGraph 之时间旅行 / 流式处理 / 持久执行 | 待做 | 待做 |
| 工程化 | day17 | Skill 从入门到精通 | 待做 | 待做 |

## 已完成内容

### 笔记

| 文件 | 覆盖内容 |
| --- | --- |
| [notes/Linux与Docker容器化基础.md](notes/Linux与Docker容器化基础.md) | 预习1–3：Linux 发行版与常用命令、权限与链接、vim、systemd、进程；Docker 镜像/容器/数据卷/Dockerfile；Compose 服务编排 |
| [notes/FunctionCalling与FastMCP-MCP协议与服务端开发.md](notes/FunctionCalling与FastMCP-MCP协议与服务端开发.md) | day01–day02：Function Calling 七步流程与 tools 说明书、反射调用与二次请求消息结构；MCP 架构与三种传输方式（Streamable HTTP / stdio / SSE 弃用）、生态入口、12306 server 部署；FastMCP 三大组件 Tool/Resource/Prompt、中间件、三种客户端接入；AI 股票小助手（东方财富接口）与 AI PC 助手（注册表读软件）两个案例 |

### 实操

| 目录 | 内容 | 验证方式 |
| --- | --- | --- |
| [hands-on/linux-docker-compose-deploy](hands-on/linux-docker-compose-deploy) | 把预习三课串成一条链路：Linux 基础操作 → redis/nginx 单容器 → Dockerfile 构建 Flask 访问计数应用 → Compose 编排 redis+web+nginx → 镜像 commit/save/load 迁移 | 在本机 WSL2 Ubuntu 24.04 + Docker 29.1.3 真机跑通，5 个阶段脚本 + 运行日志存于目录内 |

## 运行环境

实操统一在本机 WSL2 里执行，避免依赖云服务器：

| 项 | 版本 |
| --- | --- |
| WSL2 发行版 | Ubuntu 24.04.5 LTS（rootfs 离线导入，D 盘） |
| Linux 内核 | 6.18.54.1-microsoft-standard-WSL2 |
| Docker Engine | 29.1.3（systemd 托管，overlayfs） |
| Docker Compose | v2.40.3 |
| 镜像加速 | docker.m.daocloud.io / docker.1ms.run / docker.1panel.live |
| apt / pip | 清华源 |

课件用 CentOS + VMware，这里用 Ubuntu + WSL2 等价替代：`yum/dnf` ↔ `apt`，`systemctl` 用法一致。

## 约定

- 笔记文件按知识点命名，不带 `dayXX`、`预习X` 这类课次前缀
- 实操目录按关键知识点命名，一个实操一个子目录，内含源码、脚本、日志
- 只记录真跑通的内容；没跑起来的部分在对应 README 里写明现象与已尝试步骤
- 目录名统一英文 kebab-case，避免中文路径在 URL 中被编码
