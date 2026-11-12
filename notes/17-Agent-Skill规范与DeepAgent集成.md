# Agent Skill 规范与 DeepAgent 集成

> 来源课件：`python山顶会三期/day17-Skill从入门到精通`
> 材料：课堂笔记 `day21-课堂笔记.md` + `PythonProject.rar` 内 `skill_learn/`（四个教学技能与 DeepAgent 快速上手）和 `DeepAgentSkill/`（天气、邮件两个技能的实际运行项目）

## 一、Skill 是什么

AI 调用能力的演进是层层上移的，不是替代关系：

```
function calling  →  MCP  →  Skill
   调哪个函数          工具怎么跨进程共享      一类任务怎么做
```

- `function calling`：模型决定调哪个函数，参数由 schema 约束
- `MCP`：把工具做成跨进程、跨平台的服务，解决「工具分发」
- `Skill`：把做事的流程整体打包成可发现的文件夹，解决「流程复用」

定义：Skill 是智能体完成特定任务的标准化、可复用能力模块。本质就两样东西——**预设提示词 + 已经写好的方法或脚本**。

一句话理解：遇到某类问题不用现场推理，直接照着写好的步骤干完。

课件里的类比很贴切：下班回家走路要 30 分钟；会骑车之后 10 分钟。Skill 就是给 Agent 装的那辆自行车，人还是那个人，能力被放大了。

四条好处：

1. 不用把同一件事教一百遍，流程写一次就固定下来
2. 有约束就稳定，模型不会每次自由发挥
3. 可以组合，搜索 + 总结 + 生成 PPT 拼起来就是一个新技能
4. 可以共享和售卖，像插件一样装到别的工具里

来历：Anthropic 在 2025 年 10 月提出 Agent Skills 规范，开放标准，2026 年 3 月社区生态起来之后被 Trae、Claude Code、OpenClaw 等一批工具采纳。

入口清单：

| 类型 | 地址 |
| --- | --- |
| 官方技能库 | github.com/anthropics/skills |
| 标准文档 | agentskills.io |
| 社区仓库 | github.com/agentskills/agentskills |
| 市场 | skillsmp.com、skillhub.tencent.com、modelscope.cn/skills |

## 二、标准结构与 SKILL.md

目录结构里只有 `SKILL.md` 是必需的：

```
my-skill/                # 目录名即技能名，命名有硬规则
├── SKILL.md             # 必需：YAML 元数据 + Markdown 指令
├── scripts/             # 可选：确定性代码，Python / Bash
├── references/          # 可选：API 手册等参考资料，按需查阅
└── assets/              # 可选：模板、图片等静态资源
```

实际交付时凑齐四个目录不是硬要求，一个文件夹放 `SKILL.md` + 一个脚本就能用。

`SKILL.md` 由两段组成。

**头部 YAML 元数据**，用 `---` 包裹，是 AI 判断「是否加载此技能」的唯一依据：

```yaml
---
name: my-skill-name      # 必填，必须与文件夹名完全一致
description: 当用户需要处理 PDF 文件时触发，包括提取文本、合并文档或填写表单。
version: "1.0.0"         # 可选
author: your-name        # 可选
---
```

命名规则很硬：只允许小写字母、数字、连字符。`send-email` 对，`send_email` 和 `SendEmail` 都错。

`description` 要写成「做什么 + 什么时候用」，这一句直接决定触发准确率。

**正文 Markdown 指令**，是执行任务的现场手册，建议四块：

1. 角色定义：你现在是谁（如「资深文档处理助手」）
2. 触发条件：什么话术下该用
3. 执行步骤：编号写清 1 → 2 → 3，不给模型留猜测空间
4. 工具使用：怎么调 `scripts/` 里的代码，命令模板、参数必填项、依赖

## 三、三个递进案例

### 3.1 纯指令型：月报生成器

`monthly-report-generator` 没有一行脚本，全靠说明书约束输出。

结构就是四小节：

- 使用场景：行业简报、数据总结、趋势分析
- 执行步骤：提关键词与时间范围 → 联网搜索 → 过滤低质内容 → 提取核心数据、事件、风险 → 按固定格式输出
- 输出格式：`【标题】【核心数据】【重要趋势】【风险提示】`
- 异常处理：无结果返回「未找到相关信息」，搜索失败重试 1 次仍失败就报错

适用边界：流程本身用模型现有能力就能走完的（搜索 + 总结 + 排版），写说明书就够。

### 3.2 指令 + 脚本型：PDF 合并

`pdf-merger` 两个文件：`SKILL.md` + `process.py`。

说明书负责三件事：角色（文档处理助手）、触发条件（「合并 PDF」「把这几个文件合在一起」）、四步执行（确认文件 → 调 `python process.py` → 验证输出可打开 → 反馈路径），再补两条注意事项（文件不存在要提示、默认输出名 `merged_output.pdf`）。

脚本只干一件事：`PdfMerger` 循环 `append`，最后 `write` + `close`。

这里的分界线值得记住：**决策留给模型，确定性操作交给脚本**。拼接 PDF 字节这种活模型做不了，也不能交给它做。

### 3.3 可交付型：天气与邮件

`get-weather` 和 `sendemail` 是同构的两个技能，脚本都写成 CLI：

```bash
# SKILL.md 里写的调用模板（路径相对技能目录）
../.venv/Scripts/python get_weather.py --city "潍坊"
../.venv/Scripts/python send_email.py --to "xx@qq.com" --subject "会议提醒" --body "明天下午3点"
```

要点四条：

1. 脚本路径是相对技能目录算的，venv 建在项目根就得写 `../.venv`
2. 参数用 `argparse` 声明 `required=True`，缺参立刻报错，不让模型猜
3. 说明书里逐个标注参数是否必填
4. 邮件脚本要连 SMTP，先开服务拿授权码

SMTP 主机与端口：

| 邮箱 | 服务器 | TLS | SSL |
| --- | --- | --- | --- |
| Gmail | smtp.gmail.com | 587 | 465 |
| Outlook | smtp.office365.com | 587 | 465 |
| QQ | smtp.qq.com | 587 | 465 |
| 163 | smtp.163.com | 25 | 465 |
| Yahoo | smtp.mail.yahoo.com | 587 | 465 |

坑在授权码上：QQ 和 163 要在邮箱设置里开启 SMTP 服务后生成授权码，它跟登录密码不是一回事；Gmail 要开「低安全性应用访问」或者用应用专用密码。

## 四、平台落地一：Trae

把写好的技能导入 Trae 的流程：

1. 安装 Trae，注册登录
2. 打开一个项目目录
3. 设置 → 规则和技能 → 技能 → 创建，作用域选**全局**（所有项目可用）或**项目**（仅当前项目）
4. 技能目录压成 zip 导入
5. 正常对话提需求，命中 `description` 就会自动调用

判断有没有生效：对话过程里能看到读取 `SKILL.md`、执行脚本的动作，而不只是回一段文字。

同一个技能包在 Trae、Cursor、Claude Code、OpenClaw 之间通用，这正是标准的意义。

## 五、平台落地二：LangChain 生态

先说现状：**LangChain 和 LangGraph 官方还没原生支持 `SKILL.md` 标准**，DeepAgent 已经支持 `skills` 参数。

### 5.1 LangChain / LangGraph / DeepAgent 三层关系

| 维度 | LangChain | LangGraph | DeepAgent |
| --- | --- | --- | --- |
| 定位 | LLM 应用基础组件库 | 工作流编排引擎 | 高阶自主智能体框架 |
| 抽象层级 | 低（组件级） | 中（流程级） | 高（任务级） |
| 核心能力 | 模型、工具集成、简单链 | 图结构、状态、持久化、多 Agent | 自动规划、文件系统、子 Agent |
| 执行模式 | 线性 Chain | 有向图，支持循环与分支 | 基于 LangGraph 的自主执行 |
| 开发难度 | 低 | 中 | 极低 |

比喻：LangChain 是积木箱，LangGraph 是流程图加调度器，DeepAgent 是装好的成品机器人。LangChain v1.0 之后的 Agent 本来就跑在 LangGraph 上，DeepAgent 再往上封装一层。

### 5.2 DeepAgent 最小用法

```python
from deepagents import create_deep_agent

agent = create_deep_agent(
    model=model,
    tools=[get_weather],
    system_prompt="你是一个有用的小助手",
)
res = agent.invoke({"messages": [{"role": "user", "content": "上海的天气如何"}]})
```

### 5.3 DeepAgent 挂载技能目录

```python
from deepagents.backends.filesystem import FilesystemBackend
from langgraph.checkpoint.memory import MemorySaver

agent = create_deep_agent(
    model=model,
    backend=FilesystemBackend(root_dir=r"D:\project\DeepAgentSkill"),
    skills=[r"D:\project\DeepAgentSkill\skills"],
    checkpointer=MemorySaver(),
)
```

三个参数各管一件事：

- `backend`：给智能体一个真实文件系统，技能里的脚本要靠它落盘执行
- `skills`：技能目录列表，指向装着各个技能文件夹的父目录
- `checkpointer`：多轮状态，调用时配 `thread_id` 才能记住上下文

### 5.4 LangGraph 里怎么用

没有原生支持时的做法：把 `SKILL.md` 的流程写进系统提示词或工具 docstring，把脚本包成 `@tool` 注册给 `ToolNode`，本质等价于「把说明书硬编码进工具函数」。

课件示例是「搜索 + 摘要」两个原子技能：`@tool` 定义 → `ToolNode(skills)` 批量注册 → 条件边按模型输出路由 → 搜完回到 LLM、摘要直接结束。

要注意那段示例里的路由是字符串匹配最后一条消息（`"search_web" in last_msg`），属于教学简化写法；生产环境应该按 `tool_calls` 字段判断，否则模型随口提到工具名就会被误路由。

## 六、踩坑与边界

1. **模型支持度参差**：Claude 最稳；DeepSeek 跑普通技能可以，但发邮件这种带副作用的技能会出现「测试几次都显示成功、收件箱里却没有」；千问基本不行。带副作用的技能必须自己做结果校验，不能信模型转述的「成功」。
2. **相对路径基准是技能目录**，不是项目根。`../.venv/Scripts/python` 写成 `.venv/Scripts/python` 就到不了解释器。
3. **脚本自带参数校验**比让模型补参数可靠，`argparse` 的 `required=True` 是最低成本的一道闸。
4. **`description` 就是触发开关**，「邮件技能」和「用于发送电子邮件。当用户明确要求发送邮件、通知或消息给某人时使用」的命中率不是一个量级。
5. **大文件不进技能目录**：`references/` 放手册、`assets/` 放模板，运行产物和虚拟环境都不该打进去。
6. **分发时排除 `.venv`**：课件那个 57MB 的 rar 里绝大部分是虚拟环境，真正的技能文件只有几十 KB。

## 七、速查清单

1. Skill = 文件夹 + `SKILL.md`（YAML 元数据 + Markdown 指令），本质是提示词加脚本
2. 目录名 kebab-case，`name` 必须与目录名一致
3. `description` 写「做什么 + 何时触发」，它决定加载与否
4. 正文四块：角色 / 触发条件 / 执行步骤 / 脚本调用
5. 分界线：决策给模型，确定性给脚本
6. Trae 导入：设置 → 规则和技能 → 技能 → 选全局或项目 → 导入 zip
7. DeepAgent：`create_deep_agent(model, tools, backend, skills, checkpointer)`
8. LangGraph：把说明书塞进 system prompt 或 tool docstring，脚本包成 `@tool`
9. 有副作用的技能要自校验结果，别信「成功」字样
10. 技能能跨平台通用，这是它相对普通 prompt 的核心价值
