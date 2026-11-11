# LangGraph 时间旅行、流式处理与持久执行

> 来源：python 山顶会三期 day16（LangGraph 之时间旅行 / 流式处理 / 持久执行），课件 `day20-课堂笔记.md` + 代码包 `LangGraph_demo.zip`
> 定位：理解向笔记，记录机制、要点与踩坑，不复刻课件代码

## 0. 这份内容在讲什么

day16 是 LangGraph 基础篇的收口，四块内容全部建立在 day15 的检查点机制上：

```
人机协作改造   → 把 interrupt_before 静态断点版改写成 interrupt() 动态中断版
时间旅行       → 重放（回到某检查点继续执行）、分支（改状态开新时间线）
流式处理       → 节点级 stream() + 令牌级 messages 模式 + HITL 混合流
持久执行       → 崩溃恢复、精确一次执行（幂等）、断点续跑
```

主线一句话：**检查点存的是「每一超级步的快照 + 一个可寻址的 checkpoint_id」，时间旅行 = 拿着某个 id 重新 invoke，持久执行 = 拿着最新的 id 继续 invoke。**

## 1. 人机协作改造：从静态断点到动态中断

day15 结尾的审批 Demo 用 `compile(interrupt_before=["pay"])`，作业要求改成 `interrupt()` 版本。改造前后对比：

| | interrupt_before（静态） | interrupt()（动态） |
| --- | --- | --- |
| 位置 | 编译时指定节点名前/后 | 节点代码里任意一行 |
| 条件性 | 无（到点必停） | 可 if 判断（金额 >1000 才停） |
| 恢复 | `update_state` 改完再 `invoke(None)` | `Command(resume=…)` 直接把值送回 interrupt |
| 中断信息 | 看 `get_state().next` | `result["__interrupt__"]` 里的 payload |

改造后的核心节点：

```python
def check_amount(state):
    if state["amount"] > 1000:
        response = interrupt({"reason": "金额过大，需要人工审批"})
        return {"status": response, "log": [log_entry]}     # resume 的值直接落进 state
    return {"status": "auto_approved", "log": [log_entry, "自动批准"]}

result = graph.invoke(initial_state, config)
if result.get("__interrupt__"):
    result = graph.invoke(Command(resume=input("approved / reject: ")), config)
```

注意条件边也顺势改了：`lambda s: "pay" if s["status"] == "approved" else END`——中断前 status 是 pending，恢复后才是 approved/reject，边判断必须用恢复后的值。

## 2. 时间旅行（Time Travel）

课件定义：时间旅行是对检查点**历史回溯能力**的形象称呼——回到任意历史步骤，查看/修改当时的状态，再重新往后跑。普通对话只能单向向前，时间旅行可以「回到第 3 轮改一下再重放」。

三个必须掌握的动作：**查历史 → 重放 → 分支**。

### 2.1 重放：拿 checkpoint_id 再 invoke

```python
history = list(graph.get_state_history(config))       # 倒序：最新在前
for s in history:
    print(f"next={s.next}, checkpoint_id={s.config['configurable']['checkpoint_id']}")

before_joke = next(s for s in history if s.next == ("write_joke",))   # 找「写笑话」执行前
replay_result = graph.invoke(None, before_joke.config)                # 从这个检查点继续
```

`s.next` 是**接下来要执行的节点元组**，用它定位「某节点执行前」的快照最可靠。执行效果：`generate_topic` 不会重复跑，`write_joke` 重新执行——**已完成的步骤跳过，这就是「跳过已完成」语义**。

### 2.2 分支：update_state 开新时间线

重放是「原样再走一遍」，分支是「改点东西再走」：

```python
fork_config = graph.update_state(before_joke.config, values={"topic": "小鸡"})
fork_result = graph.invoke(None, fork_config)          # 用新主题重新写笑话
```

两个关键语义：
- `update_state` **不会回滚原会话**，而是基于指定检查点**新建一个检查点**（新分支），原历史完整保留；
- 返回值 `fork_config` 是新分支的 config，必须拿它去 invoke。

`as_node` 参数控制「这次状态更新算哪个节点的输出」——决定新分支从谁的后续节点开始执行：

```python
fork_config = graph.update_state(before_joke.config, values={"topic": "小鸭"}, as_node="generate_topic")
# 等价于「generate_topic 刚执行完」→ 从它的下游 write_joke 开始
```

什么时候必须显式给 `as_node`：**并行分支**（多个节点同一步更新状态，推断不出来，会抛 `InvalidUpdateError`）、**全新会话初始化状态**、**想跳过某节点**（把它下游节点当 as_node）。

### 2.3 中断场景下的时间旅行

带 `interrupt()` 的节点被重放时会**再次触发中断**，等新的 `Command(resume=…)`：

```python
replay_result = graph.invoke(None, before_ask.config)   # 又停在中途，等 resume
final = graph.invoke(Command(resume="lqz"), fork_config)  # 用新答案恢复分支
```

多中断场景（先问姓名、再问年龄）的价值最明显：在两个中断之间建分支，**前面步骤的答案保留、后面步骤的答案可以换**，不用从头再答一遍。这就是「多步骤表单改中间某一项」的底层实现。

### 2.4 子图的时间旅行：粒度问题

| 子图检查点配置 | 父图看到的粒度 | 能做到什么 |
| --- | --- | --- |
| 继承父图（子图 `compile()` 不传） | 整个子图 = 一个超级步，只生成一个检查点 | 只能从子图执行前回放，**整个子图从头重跑** |
| 子图独立（`compile(checkpointer=True)`） | 子图内部每步都有检查点 | 可以在子图内部节点之间回放/分支 |

子图独立后，从**子图自己的检查点**建分支的写法：

```python
parent_state = graph.get_state(config, subgraphs=True)
sub_config = parent_state.tasks[0].state.config      # 取子图任务的检查点 config
fork_config = graph.update_state(sub_config, {"value": ["forked"]})
graph.invoke(None, fork_config)                      # 步骤 A 的结果保留，步骤 B 重跑
```

`get_state(config, subgraphs=True)` 返回的 `tasks[0].state` 才是子图视角的检查点——不带 subgraphs 参数只能拿到父图层面的。

## 3. 流式处理（Streaming）

### 3.1 两种粒度 + 三个 API

| 粒度 | 参数 | 拿到什么 |
| --- | --- | --- |
| 节点级 | `graph.stream(input)`（默认 updates） | 每执行完一个节点推一次 `{节点名: 状态更新}` |
| 令牌级 | `stream_mode="messages"` | LLM 逐 token 的 `(chunk, metadata)` |
| 事件级 | `stream_events()` | 节点开始/结束、LLM 调用等 24 种事件，调试监控用 |

核心 API：`stream()` 同步迭代、`astream()` 异步（FastAPI 流式响应就用它）。课件强调：**流式必须配 checkpointer**（会跨线程读写检查点），SQLite 记得 `check_same_thread=False`。

节点级最小例：

```python
for chunk in graph.stream({}, config=config):
    for node_name, node_output in chunk.items():
        print(node_name, node_output.get("topic"), node_output.get("joke"))
```

### 3.2 令牌级流式与按节点过滤

```python
for chunk in graph.stream({"topic": "猫"}, stream_mode="messages", version="v2"):
    if chunk["type"] == "messages":
        msg, metadata = chunk["data"]
        if msg.content and metadata["langgraph_node"] == "write_joke":   # 只要写笑话节点的 token
            print(msg.content, end="|", flush=True)
```

`metadata["langgraph_node"]` 是过滤的关键：并行两个节点同时产出 token 时（课件例子 write_joke 和 write_poem 并行），不按节点过滤就会两路输出交织在一起。

### 3.3 流式的四种用途

实时展示多节点进度、LLM 逐字输出、**流式捕获中断信号**（HITL 前面讲过的 `stream_mode=["messages","updates"]` + `__interrupt__` 检测）、FastAPI 里非阻塞响应。

## 4. 持久执行（Durable Execution）

### 4.1 原理：检查点 + 执行游标 + 恢复

一句话：**每一步都把状态写进 checkpointer，崩溃/重启后再 `invoke(None, config)`，LangGraph 读检查点跳过已完成的节点，从中断处继续。**

四个要素：检查点（存状态、位置、节点输出）、thread_id（执行游标）、存储后端（内存仅调试，生产用 SQLite/MySQL/Redis）、恢复逻辑（跳过已完成步骤）。

```python
conn = sqlite3.connect("durable_execution.db", check_same_thread=False)
checkpointer = SqliteSaver(conn)
graph = builder.compile(checkpointer=checkpointer)

graph.invoke({"status": "init"}, config=config)        # 跑完 generate_topic 后「崩溃」
new_graph = builder.compile(checkpointer=checkpointer)  # 模拟重启：重新编译
result = new_graph.invoke(None, config=config)          # 跳过 generate_topic，只跑 write_poem
```

注意最后一步：**重启不丢状态的关键是 checkpointer 对象连着同一个数据库文件**，图对象重新编译无所谓。

### 4.2 精确一次执行：非幂等操作的护身符

发邮件、扣款这类操作重跑一次就是事故。做法是在 state 里放一个「已执行」标记，节点开头检查：

```python
class EmailState(TypedDict):
    ...
    email_sent: bool = False

def send_email(state):
    if state.get("email_sent"):
        print("邮件已发送，跳过执行")
        return state
    return {"email_sent": True}     # 真正发送放在这里
```

`graph.invoke(None, config)` 第二次进来时 `email_sent` 已经是 True，直接跳过。配合检查点，这就是「精确一次」语义的最小实现。这跟 day15 中断铁律里「interrupt 之前的副作用要幂等」是同一个问题的两种解法：**标记位（本次会话内）vs 幂等操作（跨会话通用）**。

### 4.3 故障恢复：跳过已完成步骤

课件用 `step2` 里 50% 概率 `raise RuntimeError` 模拟崩溃：

```python
try:
    graph.invoke({"task_id": "TASK789"}, config=config)
except RuntimeError as e:
    print(f"执行失败：{e}")

result = graph.invoke(None, config=config)     # 恢复：step1 不重跑，step2 重试
```

恢复执行时 `step1` 已完成的检查点存在，直接跳过；`step2/step3` 重新执行。这就是「长任务中途崩了不用从头再来」——也是 LangGraph 宣传的 durable execution 卖点。

三个使用要求（课件原话）：必须配 checkpointer；长工作流要保证存储后端高可用；非幂等操作要结合精确一次语义。

## 5. 踩坑与要点

- 时间旅行找检查点用 `s.next == ("节点名",)` 定位「该节点执行前」，比数索引稳。
- `update_state` 只**新建分支**，不修改原历史；改完必须用返回的 `fork_config` 去 invoke。
- 并行分支下 `update_state` 不给 `as_node` 会抛 `InvalidUpdateError`。
- 重放带 interrupt 的节点会**再次中断**，需要再给一次 `Command(resume=…)`；不给就一直停着，不是 bug。
- 子图默认继承父图检查点时，**子图内部无法时间旅行**，要 `compile(checkpointer=True)`。
- `get_state(config, subgraphs=True)` 才能拿到子图任务的 config。
- 流式必须配 checkpointer；SQLite 记得 `check_same_thread=False`。
- 多节点并行流式时要按 `metadata["langgraph_node"]` 过滤，否则 token 交织。
- 崩溃恢复的前提是**同一个 checkpointer 连同一个库 + 同一个 thread_id**，三个都一致才续得上。
- 非幂等节点必须有 `email_sent` 这类标记位，否则恢复执行 = 重复执行。

## 6. 关键知识清单

- 时间旅行三动作：`get_state_history` 找快照 → `invoke(None, snapshot.config)` 重放 → `update_state` + `invoke(None, fork_config)` 分支。
- `as_node` 决定新分支从哪个节点的下游开始执行；并行/新会话/跳节点时必须显式给。
- 中断节点的重放会自动再触发中断，用新的 `Command(resume=…)` 恢复。
- 子图时间旅行粒度：继承父图 = 子图整体一个超级步；`checkpointer=True` = 子图内部每步可回溯。
- 流式两粒度：`stream()` 节点级（`{节点名: update}`）、`stream_mode="messages"` 令牌级（按 `langgraph_node` 过滤）。
- HITL 混合流：`stream_mode=["messages","updates"]` 同时拿逐字输出和 `__interrupt__` 信号。
- 持久执行 = 检查点 + thread_id + 存储后端 + 跳过已完成；重启后 `invoke(None, config)` 续跑。
- 精确一次 = state 里放「已执行」标记位，节点开头检查后跳过。
