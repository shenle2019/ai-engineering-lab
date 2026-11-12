# Agent Skill 规范与 DeepAgent 集成

把 day17「Skill 从入门到精通」的课件内容做成一套**真的能跑**的本机运维技能集：四个 `SKILL.md` + 三个脚本，挂到 DeepAgent 上，让模型自己按说明书取数据、写报告。

课件的示例技能（查天气、发邮件、合并 PDF）都依赖外部服务，本地复刻只能验证「目录结构对不对」，验不了「模型会不会照着做」。这里换成本机运维场景——磁盘、日志、端口——所有数据都能当场核对，技能写得好不好，从工具调用轨迹里一眼能看出来。

## 来源

- 课件：`python山顶会三期/day17-Skill从入门到精通`（课堂笔记 821 行 + `PythonProject.rar`）
- 笔记：[notes/17-Agent-Skill规范与DeepAgent集成.md](../../notes/17-Agent-Skill规范与DeepAgent集成.md)
- 课件原文的技术结论在笔记里，这里只记录复刻时实际跑出来的东西

## 技能集设计

四个技能按「采集」和「撰写」分工，验证的是两种技能形态：

| 技能 | 形态 | 做什么 |
| --- | --- | --- |
| `disk-usage` | 指令 + 脚本 | 统计目录占用与磁盘余量，`--path` / `--top` |
| `log-scan` | 指令 + 脚本 | 扫日志文件或目录，统计级别分布并给样例行 |
| `env-check` | 指令 + 脚本 | 查 Python 版本、端口监听、环境变量存在性 |
| `inspection-report` | 纯指令 | **没有脚本**，只规定报告格式与判定规则 |

`inspection-report` 是故意做成纯指令型：它没有采集能力，只能消费别的技能取回的数据。这是课件里「月报生成」那个例子的等价物，用来验证模型会不会遵守「缺数据就写未采集」这类约束。

目录结构按官方规范：

```
skills/
└── disk-usage/
    ├── SKILL.md          # YAML front matter（name/description）+ 正文四块
    └── disk_usage.py     # 只在正文「脚本调用」里被引用
```

`name` 必须与目录名完全一致、只能 kebab-case，这条由 `s01` 强制校验。

## 环境

| 项 | 版本 |
| --- | --- |
| OS | Windows 10（22H2） |
| Python | 3.11.9（venv 在目录内 `.venv/`） |
| deepagents | 0.7.35 |
| langchain / langchain-core / langchain-openai | 1.5.0 / 1.8.0 / 1.7.4 |
| langgraph | 1.2.20 |
| LLM | DeepSeek `deepseek-chat`（OpenAI 兼容端点），key 只走环境变量 `DEEPSEEK_API_KEY` |
| 安装源 | 阿里云（清华源对 `deepagents` 返回 403） |

## 目录

```
06-agent-skill-and-deepagent/
├── skills/                     # 四个技能，DeepAgent 挂载的就是这个目录
├── samples/app.log             # 巡检用的样例日志（含 1 CRITICAL / 3 ERROR / 5 WARN / 15 INFO）
├── stages/
│   ├── stages_common.py        # 公用 Agent 配置与轨迹打印
│   ├── s01_validate_skills.py  # 技能目录合规校验（纯静态，不调模型）
│   ├── s02_scripts_only.py     # 绕过 Agent 直接跑三个脚本（含异常路径）
│   ├── s03_deepagent_single.py # 单技能调用
│   ├── s04_multi_skill.py      # 多技能编排 + 报告落盘
│   └── s05_boundary.py         # 技能覆盖不到 / 脚本报错时的表现
├── run_inspection.py           # 综合案例入口：一条命令跑完巡检
├── reports/                    # 报告输出（.gitignore 排除，保留 .gitkeep）
└── logs/                       # 各阶段实跑日志，含两份 virtual_mode 对照
```

## 运行

```powershell
cd hands-on/06-agent-skill-and-deepagent
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

$env:DEEPSEEK_API_KEY = "sk-..."
$env:PYTHONUTF8 = "1"

.\.venv\Scripts\python.exe stages\s01_validate_skills.py
.\.venv\Scripts\python.exe stages\s02_scripts_only.py
.\.venv\Scripts\python.exe stages\s03_deepagent_single.py
.\.venv\Scripts\python.exe stages\s04_multi_skill.py
.\.venv\Scripts\python.exe stages\s05_boundary.py
.\.venv\Scripts\python.exe run_inspection.py
```

不装 venv 也能跑 `s01`（只读文件、只依赖 PyYAML）和三个技能脚本本身（纯标准库）。

## 各阶段验证点与结果

| 阶段 | 验证什么 | 结果 |
| --- | --- | --- |
| s01 | front matter 可解析、`name` 等于目录名、kebab-case、`description` 够具体、正文引用的脚本真实存在 | 4 个技能全 PASS |
| s02 | 正常参数输出可解析；缺参数、路径不存在必须非零退出 | 5/5 PASS |
| s03 | 技能元数据注入模型上下文；模型读 SKILL.md 后执行脚本；回答里的数字与脚本输出一致 | PASS，工具调用 3 次 |
| s04 | 一次提问编排三个采集技能 + 一个撰写技能；报告四节齐全；日志条数与脚本基准一致；文件落盘 | PASS，工具调用 12 次 |
| s05 | 没有对应技能时明确说做不到；路径不存在时如实报错、不编条数 | PASS，6 + 2 次调用 |
| 综合 | 一条命令完成技能自检 → 采集 → 报告落盘 | PASS，11 次调用，报告 1125 字符 |

`s02` 的 5 个检查是：磁盘正常路径、磁盘路径不存在、日志正常路径、日志缺 `--path`、运行时端口与变量。

## 关键结论（和课件不一致的地方）

### 1. `FilesystemBackend` 跑不了技能脚本

课件写法：

```python
backend = FilesystemBackend(root_dir=r"D:\project\DeepAgentSkill")
agent = create_deep_agent(model=model, backend=backend, skills=[...])
```

本机 deepagents 0.7.35 里 `FilesystemBackend` 只有 `read/write/ls` 一类方法，**没有 `execute`**。模型能读到 `SKILL.md`，读到「执行这条命令」就卡住。

要让技能脚本真的跑起来，必须换 `LocalShellBackend`：

```python
from deepagents.backends import LocalShellBackend
backend = LocalShellBackend(root_dir=str(ROOT), virtual_mode=True, timeout=120, inherit_env=True)
```

代价是 shell 直接在宿主机上跑、没有沙箱隔离，官方文档也标注了这一点。只适合本机开发场景。

### 2. `virtual_mode` 两个值都有坑

| 配置 | 现象 | 调用次数 |
| --- | --- | --- |
| `True` + SKILL.md 里写 `../../.venv/...` | 模型把 `/skills/...` 当 shell 路径去 `cd`，连错 6 次 | 18 |
| `False` | `read_file` 直接报 `Windows absolute paths are not supported`；`ls("/")` 把整块 E 盘目录树倒给模型 | 11 |
| `True` + SKILL.md 明写路径约定 + `..\..\` | 1 次 `read_file` + 1 条 `execute` | 3 |

原因：`virtual_mode` **只作用于文件工具**，`execute` 的工作目录始终是真实 `root_dir`。文件侧看到的是 `/skills/disk-usage/SKILL.md`，shell 侧看到的是 `E:\...\06-agent-skill-and-deepagent`，模型很容易把两套路径混起来。

两份对照日志留在 `logs/s03_virtual_mode_true.log`（18 次）和 `logs/s03_virtual_mode_false.log`（11 次），最终版是 `logs/s03_deepagent_single.log`（3 次）。

### 3. `inherit_env=False` 会让 Windows socket 直接崩

`LocalShellBackend` 默认不继承环境变量。子进程里没有 `SYSTEMROOT`，`socket.socket()` 报：

```
OSError: [WinError 10106] 无法加载或初始化请求的服务提供程序
```

表现很有迷惑性：`env_check.py` 打印完 Python 版本和系统就退出 1，一句错误都不说（traceback 走到 stderr）。同时 `DEEPSEEK_API_KEY` 会被报成「未设置」——变量确实不在子进程环境里。

三处一起改才彻底：

1. `LocalShellBackend(..., inherit_env=True)`
2. `env_check.py` 把 `socket` 包进 `try/except OSError`，把「探测失败」和「未监听」分开上报
3. 技能脚本一律只报变量存在性，不回显值

### 4. `execute` 用 UTF-8 解码 Windows 中文输出会截断

模型跑 `dir` 这类输出 GBK 的命令时，deepagents 侧会抛 `UnicodeDecodeError`，输出停在半个汉字处，模型看到的是「命令成功但没输出」。规避办法是让技能脚本自己 `sys.stdout.reconfigure(encoding="utf-8")`，并且不要在技能里调 `dir`、`chcp` 这类本地产出 GBK 的命令。

### 5. 技能目录不参与打包

课件里 `PythonProject.rar` 有 57 MB，其中 `.venv` 占绝大部分。技能仓库提交时排除 `.venv/`、`__pycache__/`、`.env`，`reports/*.md` 也不入库（每次内容随机器变化）。

## 与课件的取舍

| 课件 | 这里 | 原因 |
| --- | --- | --- |
| 天气 / 邮件 / PDF 合并技能 | 磁盘 / 日志 / 端口 / 报告 | 课件示例依赖外部服务与凭证，本地无法核对数字真假 |
| `FilesystemBackend` | `LocalShellBackend` | 前者跑不了脚本，见结论 1 |
| 每个技能示例单独跑 | 四个技能编排成一条巡检链路 | 单技能只能验证「能调」，多技能才能验证「按说明书协作」 |
| Trae 里导入 zip | 未做 | 需要 GUI 手工操作，无法脚本化验证 |
| 模型支持度一笔带过 | s05 专门测边界 | 技能覆盖不到时会不会编，比会不会用更值得测 |

## 踩坑记录

1. 清华源 `403 Forbidden` → 换阿里云镜像
2. `deepagents` 0.7.35 的 `LocalShellBackend` 不在 `deepagents.backends.filesystem`，在 `deepagents.backends.local_shell`（`from deepagents.backends import LocalShellBackend` 可用）
3. PowerShell 下 `../../.venv/Scripts/python.exe` 被 cmd 解析成命令 `..` → 技能里的相对路径统一写 `..\..\.venv\Scripts\python.exe`，代码块语言标 `bat`
4. `log-scan/SKILL.md` 初版把代码围栏写成了 `--limit 5``` `（反引号少一个），`s01` 查不出来，靠人眼发现后修正
5. `virtual_mode=False` 时 `read_file` 完全不可用，模型退化成用 `type`/`dir` 读文件，日志里能看到这条退化路径
6. 报告类技能必须写死输出节标题，否则模型每次结构都不一样，`s04` 的「四节齐全」检查就是靠这个卡住的
