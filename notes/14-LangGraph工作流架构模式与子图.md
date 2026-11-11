# LangGraph 工作流架构模式与子图

> 来源：python 山顶会三期 day14（LangGraph 核心架构模式和子图），课件 `day18-课堂笔记.md` + 代码包 `LangGraph_demo.rar`
> 定位：理解向笔记，记录机制、要点与踩坑，不复刻课件代码

## 0. 这份内容在讲什么

day13 学会了「怎么画图」，day14 回答「**该画成什么形状**」。课件把 LangGraph 官方那篇 agent-building-workflows 文档的六种模式全部落成可跑的代码，再补一个子图（Subgraph）：

```
LLM 增强      → 工具调用 / 结构化输出 / 记忆，是所有模式的地基
提示链        → 线性管道，中间加 gate 判断
并行化        → 同一输入多路同时跑，再聚合
路由          → LLM 用结构化输出决定走哪条分支
编排者-工作者 → Send API 动态派发，章节数不固定也能 fan-out
评估者-优化器 → 生成 ↔ 评估循环，直到达标
Agent         → 自己决定调什么工具的 ReAct 循环
子图          → 把一张图封装成父图的一个节点（父图 = 电脑，子图 = 内存/硬盘/CPU）
```

主线记忆法：**前五种是「开发者定流程、LLM 在节点内干活」的工作流；最后一种是「LLM 定流程」的 Agent。** 子图则是把任意一种模式打包复用。

## 1. 地基：LLM 增强

三个增强手段在 day04–day07 都学过，这里是把它们作为「工作流节点内部的零件」再确认一遍：

```python
structured_llm = llm.with_structured_output(SearchQuery)   # 结构化输出：schema 即约束
llm_with_tools = llm.bind_tools([multiply])                # 工具调用：模型返回 tool_calls
```

结构化输出在 day14 的地位非常高——**路由和评估两个模式的核心就是把「判断」变成 schema 字段**（`Literal` 枚举），彻底替代 if-else 里塞 prompt 的老办法。

## 2. 七种模式逐一看

### 2.1 提示链（Prompt Chaining）

线性管道：每一步的输出是下一步的输入，中间可以用代码 gate 决定「继续加工」还是「直接交卷」。

课件案例是笑话生成器：`generate_joke → check_punchline`，笑话里含 `!` 就算过关直接 END，否则走 `improve_joke → polish_joke` 两条加工链再 END。

```python
workflow.add_conditional_edges(
    "generate_joke",
    check_punchline,                       # 返回 "Pass" / "Fail"
    {"Fail": "improve_joke", "Pass": END},
)
```

要点：gate 判断可以是纯 Python（比 LLM 便宜稳定），条件边第三参用 dict 把返回值映射到节点名，比函数内部直接返回节点名更清晰。课件结尾用 `if "improved_joke" in state` 判断走了哪条分支——**State 字段存在与否本身就是执行轨迹的证据**。

典型用途：翻译流水线、先提纲后正文、草稿 → 审校 → 定稿。

### 2.2 并行化（Parallelization）

同一个输入同时喂给多个独立子任务，最后聚合：

```python
parallel_builder.add_edge(START, "call_llm_1")   # 笑话
parallel_builder.add_edge(START, "call_llm_2")   # 故事
parallel_builder.add_edge(START, "call_llm_3")   # 诗
parallel_builder.add_edge("call_llm_1", "aggregator")
# …三个节点都指向 aggregator
```

两种动机：**拆任务提速度**（笑话/故事/诗各自生成），**跑多份提置信度**（同一文档按格式、内容、创新性三个标准各评一次再汇总）。聚合节点等全部上游完成才执行——LangGraph 会自动处理好这一步的同步。

课件图片里可以看到三路节点在图上确实是并排扇出的结构，这是 `add_edge(START, x)` 连写三条的自然结果，不需要特殊 API。

### 2.3 路由（Routing）

先判断输入类型，再转给专用流程。核心两步：

```python
class Route(BaseModel):
    step: Literal["poem", "story", "joke"] = Field(description="The next step …")

router = llm.with_structured_output(Route)

def llm_call_router(state):
    decision = router.invoke([SystemMessage(...), HumanMessage(content=state["input"])])
    return {"decision": decision.step}      # 一定落在枚举里，不用解析文本
```

然后条件边按 `state["decision"]` 分发到 `llm_call_1/2/3`。

**亮点是用结构化输出替代硬编码规则**：`Literal` 把模型的输出锁死在合法路由上，比「让模型输出 story/poem 然后自己 startswith 判断」稳一个量级。工程上的对应场景：客服分流（定价/退款/退货）、多语言分流、按意图选工具集。

### 2.4 编排者-工作者（Orchestrator-Worker）

子任务数量事先不知道时用这个模式（路由和并行都要求分支固定）。课件案例：给一个报告主题，生成大纲 → 每个章节派一个 worker 并行写 → 汇总。

关键在 **Send API** 和两个 State：

```python
class State(TypedDict):
    topic: str
    sections: list[Section]                                  # 大纲
    completed_sections: Annotated[list, operator.add]        # 工作者结果汇总（reducer 拼接）
    final_report: str

def assign_workers(state: State):
    return [Send("llm_call", {"section": s}) for s in state["sections"]]  # 一章一个 worker
```

几个必须记住的点：
- `Send("节点名", 参数)` 返回的是**列表**，每个元素动态创建一个 worker 实例，各带独立输入；
- worker 只写一个节点函数 `llm_call(state: WorkerState)`，**最后并发几个由大纲章节数决定**；
- worker 只拿到自己那份 `WorkerState`（`{"section": ...}`），不是父图全量 state——这是 Send 与普通条件边的本质区别；
- 结果靠 `Annotated[list, operator.add]` 自动合并回父 state，编排者才能拿到全部章节。

这个模式在真实工程里就是「不定长 fan-out」：多文件批量改代码、多文档分别审查、多小节分别写。

### 2.5 评估者-优化器（Evaluator-Optimizer）

有明确成功标准、但一次做不好的任务，用「生成 → 评估 → 不满意带着反馈重生成」的循环：

```python
class Feedback(BaseModel):
    grade: Literal["funny", "not funny"]
    feedback: str        # 不通过时给改进意见

evaluator = llm.with_structured_output(Feedback)
```

生成节点看 `state.get("feedback")` 决定是首轮创作还是按反馈修改；评估节点把 `grade` 和 `feedback` 写回 state；条件边 `route_joke` 按 `"Accepted" / "Rejected + Feedback"` 映射到 END 或回到生成节点。

和提示链的区别：**提示链是单向的，评估者-优化器有回边**——这是 day13 学会的第一个循环模式的「LLM 判断版」（对比智能导游用的是 Python 判断）。翻译、写作打磨、代码修复都适合。

### 2.6 Agent（ReAct）

和 day13 的六步完全同构：`llm_call`（决策节点）→ `should_continue` 看 `last_message.tool_calls` → `tool_node` 执行工具 → 回到 `llm_call`。区别只是这里直接用现成的 `from langgraph.graph import MessagesState`，不用自定义。

判断标准：**问题和解法不可预测、步骤数不确定 → Agent；流程能提前画出来 → 用前五种工作流。**

### 2.7 模式选型速查

| 模式 | 什么时候用 | LangGraph 关键 API |
| --- | --- | --- |
| 提示链 | 步骤固定、有先后依赖 | `add_edge` + 条件边 gate |
| 并行化 | 子任务互相独立（提速）或要多次采样（提置信） | 多个 `add_edge(START, x)` + 聚合节点 |
| 路由 | 输入类型决定走哪条专用流程 | `with_structured_output(Literal)` + 条件边 |
| 编排者-工作者 | 子任务数量运行时才知道 | `Send` 列表 + `operator.add` reducer |
| 评估者-优化器 | 有明确标准、需要迭代打磨 | `with_structured_output` + 回边循环 |
| Agent | 步骤与工具不可预测 | `MessagesState` + 工具节点 + 条件边 |

## 3. 子图（Subgraph）

### 3.1 是什么、为什么

把**一张完整的图编译后当作另一张图的节点**。课件比喻：父图是电脑，子图是内存、硬盘、CPU、主板——用电脑的人不需要关心内存怎么实现。

四个价值：模块化拆分（主图只做编排）、逻辑复用（「摘要+评分」子图多个父图共用）、状态隔离（子图可以有私有字段）、团队协作（对齐输入输出接口即可独立开发）。

### 3.2 两种写法（必须分清）

**写法 A：在节点函数内调用子图**（课件说「复杂但好理解」）

```python
def call_subgraph_node(state: ParentState):
    sub_input_state = {"sub_input": state["parent_input"]}          # 父 → 子的自定义转换
    sub_output_state = subgraph.invoke(sub_input_state)             # 节点内调完整子图
    return {"parent_output": sub_output_state["sub_output"]}        # 子 → 父的转换
```

父子图 state 结构可以完全不同，转换逻辑自己写，调用前后还能加日志、异常处理、校验。代价是子图内部对父图是黑盒。

**写法 B：把编译好的子图直接 add_node**（课件标注「最好」）

```python
parent_builder.add_node("subgraph_node", subgraph)   # 就这一行
```

前提：**父子图必须共享 state 结构（字段名一致）**，LangGraph 自动传状态，零胶水代码。这也是后续课程里子图的主要用法——day15 的持久化继承、day16 的时间旅行都以这种写法为前提。

### 3.3 选择依据

| | 节点内调用 | add_node 直接挂 |
| --- | --- | --- |
| 状态结构 | 可完全不同，手写转换 | 必须一致（或子集关系） |
| 代码量 | 多（桥接逻辑） | 一行 |
| 可控性 | 强（前后可加逻辑） | 弱 |
| 图可视化 | `xray=True` 才展开内部 | 同左 |
| 后续高级能力 | 检查点、中断行为需注意 | 持久化/时间旅行支持最好 |

看子图时记得开 `get_graph(xray=True)`，否则只能看到父图层面一个黑盒节点。

## 4. 踩坑与要点

- **`Send` 的返回值必须是列表**，写出单个 `Send(...)` 会报错；它的 dict 参数会成为 worker 的**整个输入 state**，别把父图大 state 整个塞进去。
- worker 结果字段不加 `Annotated[list, operator.add]` 会被后完成的覆盖前一个——并行 + 列表结果几乎一定要 reducer。
- `with_structured_output` 的 schema 字段用 `Literal` 枚举，路由/评分才不会出非法值；prompt 里再强调一遍取值集合更稳。
- 条件边三种写法（返回节点名 / dict 映射 / 直接传列表）别混用；映射 dict 适合 gate 返回值是业务语义（"Pass"/"Fail"）而不是节点名的场景。
- 并行化聚合节点要等所有上游完成，**不等于每条分支都成功**；某条分支抛异常整张图失败，重试要放在分支节点内部。
- 子图写法 B 要求 state 字段对齐，字段名差一个就是运行时静默不传值——这是最费时间的坑。
- `xray=True` 只影响可视化，不影响执行。

## 5. 关键知识清单

- 六种工作流模式 + Agent，选型看「子任务是否可预定义、数量是否固定、是否需要迭代」。
- 提示链 = 线 + gate；并行 = 扇出 + 聚合；路由 = 结构化输出 + 条件边映射。
- 编排者-工作者 = `Send` 动态 fan-out + reducer 合并，是唯一能处理「运行时才知道几个子任务」的模式。
- 评估者-优化器 = 生成 ↔ 评估的回边循环，评估结果也是结构化输出。
- 子图两种挂法：节点内 `subgraph.invoke()`（自定义转换）与 `add_node(name, subgraph)`（共享 state、一行搞定、后续高级能力首选）。
- 子图的价值是模块化 / 复用 / 隔离 / 并行开发；可视化用 `get_graph(xray=True)`。
