# LangGraph 记忆、中断与持久化

> 来源：python 山顶会三期 day15（LangGraph 之子图 / 记忆 / 中断 / 持久化），课件 `day19-课堂笔记.md` + 代码包 `LangGraph_demo.zip`
> 定位：理解向笔记，记录机制、要点与踩坑，不复刻课件代码

## 0. 这份内容在讲什么

day15 是 LangGraph 从「能跑」到「能上线」的一课，四块内容层层递进：

```
子图持久化   → 给子图配自己的 checkpointer，thread_id 打通父子图
记忆两层     → 短期 = checkpointer + thread_id；长期 = store + user_id/namespace
管理短期记忆 → 修剪 / 删除 / 总结 / 检查点操作，解决上下文窗口有限
中断         → interrupt() 暂停 + Command(resume=) 恢复，人工参与回路（HITL）
持久化总结   → checkpoint 与 store 两大组件的全能力：查询 / 重放 / 修改 / 跨会话
```

主线：**后面所有高级能力（中断、时间旅行、持久执行）都依赖同一个前提——图配了 checkpointer。** 没有检查点，interrupt 保存不了状态，崩了没法续，时间旅行无从谈起。

## 1. 子图的持久化与流式

### 1.1 给子图单独配检查点

子图默认不持久化。要让子图自己记状态，编译时传自己的 saver：

```python
sub_saver = SqliteSaver(sqlite3.connect('sub.db', check_same_thread=False))
subgraph = sub_builder.compile(checkpointer=sub_saver)
```

父图在节点里调用子图时，**必须把 thread_id 透传下去**，否则子图找不到自己的会话：

```python
def call_subgraph_with_persist(state, config):
    sub_config = {"configurable": {"thread_id": config["configurable"]["thread_id"]}}
    return {"progress": subgraph.invoke({"task": state["task"]}, sub_config)["progress"]}
```

反过来：如果只在父图编译时传 checkpointer，LangGraph 会**自动把检查点传播给子图**（day16 时间旅行的默认行为就建立在这上面）。两种口径记住区别：

| 场景 | 写法 | 效果 |
| --- | --- | --- |
| 子图继承父图 | 子图 `compile()`，父图 `compile(checkpointer=...)` | 整个子图在父图里算一个超级步，内部节点级检查点不单独存 |
| 子图独立 | 子图 `compile(checkpointer=True)` 或自己的 saver | 子图内部每步都有检查点，可做子图级时间旅行 |

### 1.2 子图流式输出

想看到子图**内部**的执行细节，三个参数一起用：

```python
for chunk in graph.stream({"foo": "foo"}, stream_mode="updates", subgraphs=True, version="v2"):
    if chunk["type"] == "updates":
        print(chunk["ns"], chunk["data"])     # ns 是命名空间路径，能区分父图/子图节点
```

课件开场先说了一句容易被忽略的话：**流式在父子图里的主要用途是「记录子图执行到哪一步了」**，调试和前端进度条都靠它。

## 2. 记忆：短期 vs 长期

### 2.1 一张表分清

| 维度 | 短期记忆 | 长期记忆 |
| --- | --- | --- |
| 载体 | `checkpointer`（检查点） | `store`（存储引擎） |
| 标识 | `thread_id`（会话 ID） | `user_id` + `namespace` |
| 生命周期 | 会话级，删 thread_id 即失效 | 用户级，跨会话长期存在 |
| 内容 | 对话消息历史（MessagesState） | 结构化的用户/应用数据（偏好、画像、摘要） |
| 读写方式 | 自动绑定执行流程 | 手动 `put` / `search` |
| 生产替换 | InMemorySaver → Postgres/Redis/MySQL Saver | InMemoryStore → Postgres/Redis/MySQL Store |

课件的比喻很好记：短期 = 当面聊天记住刚说的话，聊完就忘；长期 = 记在笔记本上，翻本子（检索）就还在。

**两者组合用**才是真实项目的形态：AI 节点里先 `store.search` 拿用户长期偏好，再拼上当前 thread 的对话上下文，一起送给模型。豆包那种「新开对话它还记得你是谁」是长期记忆，「接着上次那个话题继续」是短期记忆。

### 2.2 短期记忆：换后端只是换一行

接口完全统一，换存储只改 saver 的构造：

```python
checkpointer = InMemorySaver()                                     # 内存，调试用
checkpointer = SqliteSaver(sqlite3.connect('demo.db', check_same_thread=False))   # 本地文件
# Redis：with RedisSaver.from_conn_string("redis://127.0.0.1:6380") as checkpointer:
# MySQL：PyMySQLSaver(pymysql.connect(...)) 或 from_conn_string(DB_URI)
# Mongo：with MongoDBSaver.from_conn_string("localhost:27017") as checkpointer:
graph = builder.compile(checkpointer=checkpointer)
config = {"configurable": {"thread_id": "1"}}      # 同一个 thread_id = 同一段会话
```

各后端的使用差异（都是实测过的坑点）：
- **RedisSaver / PyMySQLSaver / MongoDBSaver 第一次使用要 `checkpointer.setup()`** 建表/建索引，重复执行无害；SqliteSaver 不用。
- Redis / MySQL / Mongo 支持上下文管理器（`with … as`）；**SqliteSaver 不支持**，直接传 connection。
- SQLite 必须 `check_same_thread=False`，否则流式/多线程调用直接报错。
- 课件用 Docker 起 Redis：`docker run -d -p 6380:6379 redis/redis-stack:latest`（用 6380 避开本地冲突）。

### 2.3 长期记忆：Runtime 注入 + namespace

长期记忆有两个入口：编译时 `compile(store=store)`，节点里通过 `Runtime` 拿：`runtime.store`、`runtime.context`。

```python
@dataclass
class Context:
    user_id: str

def call_model(state: MessagesState, runtime: Runtime[Context]):
    namespace = (runtime.context.user_id, "memories")          # 按用户隔离
    memories = runtime.store.search(namespace, query=state["messages"][-1].content, limit=3)
    info = "\n".join(d.value["data"] for d in memories)
    runtime.store.put(namespace, str(uuid.uuid4()), {"data": "用户偏向暗色系"})
```

三个要点：
- State 类用 `StateGraph(MessagesState, context_schema=Context)` 声明上下文 schema，invoke 时传 `context=Context(user_id="1")`；
- namespace 是元组，按「用户 → 记忆类型」分层，`search` 还能按语义相似度检索（store 可绑嵌入模型）；
- **存什么不存什么由开发者决定**（`put` 是手动调用的），课件示例用「消息里出现『记住』就存一条」做最小演示。生产实现一般是让 LLM 从对话里抽取画像再写入。

生产后端同理：RedisStore / PyMySQLStore，同样 `setup()`，通常和 checkpointer 共用同一个库连接串（`with (RedisStore…, RedisSaver…)` 同时开两个上下文）。

### 2.4 管理短期记忆：四种办法

对话一长就超上下文窗口，而**每次调用 LLM 都会把整个短期记忆一次性送进去**。四种解法，课件推荐第三种：

| 办法 | 机制 | 代价 |
| --- | --- | --- |
| 修剪 `trim_messages` | 按 token 数截断，保留最后 N 个 | 丢早期信息 |
| 删除 `RemoveMessage` | 从 state 里永久删指定/全部消息 | 丢信息，且不可逆 |
| 总结 `SummarizationNode`（langmem） | 超阈值自动把旧消息压成 running summary | 多一次 LLM 调用，但信息保留最好 |
| 管理检查点 | `get_state` / `get_state_history` / `delete_thread` | 偏运维操作 |

修剪的典型调用：

```python
messages = trim_messages(state["messages"], strategy="last",
                         token_counter=count_tokens_approximately,
                         max_tokens=128, start_on="human", end_on=("human", "tool"))
```

删除必须配合 `add_messages` reducer 的 state（MessagesState 天然满足）：

```python
return {"messages": [RemoveMessage(id=m.id) for m in state["messages"][:2]]}   # 删最早两条
return {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES)]}                   # 清空
```

总结用 `langmem.short_term.SummarizationNode`：挂在 `START → summarize → call_model` 链上，state 里多一个 `context: dict[str, RunningSummary]` 存摘要，最终 `final_response["context"]["running_summary"].summary` 可读。

检查点管理三把刀：`graph.get_state(config)` 看当前值，`graph.get_state_history(config)` 列全部快照，`checkpointer.delete_thread(thread_id)` 清空整个会话——课件特意点明：**不删检查点就意味着一直保留时间旅行能力**。

## 3. 中断（Interrupt）：人工参与回路

### 3.1 机制：抛异常暂停、整节点重跑

`interrupt(payload)` 的本质是**在节点里抛一个特殊异常**让运行时捕获：保存当前状态 → 等待 → 用 `Command(resume=value)` 恢复，此时 `value` 成为 `interrupt()` 的返回值。

```python
from langgraph.types import interrupt, Command

def approval_node(state):
    decision = interrupt({"question": "是否批准该操作?", "details": state["action_details"]})
    return Command(goto="proceed" if decision else "cancel")
```

使用前提只有两条：**配了 checkpointer** + **同一个 thread_id**。首次 `invoke` 返回的 state 里会有 `__interrupt__` 字段（新版也可 `result.interrupts`），内容就是传给 `interrupt()` 的 payload；恢复时 `graph.invoke(Command(resume=True), config=config)`。

最关键的规则：**恢复时节点从头开始重新执行，不是从 interrupt 那一行继续。** interrupt 之前的代码会再跑一遍——这直接决定了下面几条规则。

### 3.2 四种常见模式

| 模式 | 做法 | 场景 |
| --- | --- | --- |
| 审批 | `interrupt({question, details})` → resume True/False → `Command(goto=…)` 分流 | 转账、删除、调外部 API |
| 审查编辑 | `updated = interrupt({instruction, content})`，返回值直接覆盖 state 字段 | 人工改 LLM 草稿 |
| 工具内中断 | 把 `interrupt()` 写进 `@tool` 函数体，模型一调工具就暂停 | 发邮件前确认，审批逻辑跟工具跑 |
| 验证人工输入 | `while True: answer = interrupt(prompt)`，非法就带着错误提示再 interrupt | 表单必填校验 |

工具内中断很实用：审批逻辑和工具绑在一起，图的其他部分复用同一工具时自动获得审批能力。课件里的 `send_email` 演示了 resume 时还能**改参数**（`{"action": "approve", "to": ...}` 覆盖原收件人）。

### 3.3 六条铁律（课件原话整理）

1. **不要用 try/except 包住 `interrupt()`**——它靠抛异常工作，被你 catch 掉就等于没中断。要保护异常代码，把 interrupt 放前面，或只捕获特定异常类型。
2. **同一个节点里多个 interrupt 的顺序必须稳定**——恢复值按索引匹配，条件跳过一个 interrupt 会导致后续错位。
3. **payload 必须是 JSON 可序列化的简单值**——不能传函数。
4. **interrupt 之前的副作用必须幂等**——节点会重跑，非幂等操作（如 create 一条审计记录）会重复执行。查询/更新是幂等的，新增不是。
5. **恢复必须用同一个 thread_id**。
6. 与「节点内调用子图」组合时：**父节点和子图节点中 interrupt 之前的代码都会重新执行**。

### 3.4 流式里的中断

HITL 前端要同时做两件事：边生成边显示（`stream_mode=["messages", "updates"]`）和在 update 里发现 `__interrupt__` 就收口等用户输入：

```python
for chunk in graph.stream(initial_input, stream_mode=["messages", "updates"],
                          subgraphs=True, config=config, version="v2"):
    if chunk["type"] == "messages":
        ...
    elif chunk["type"] == "updates" and "__interrupt__" in chunk["data"]:
        interrupt_info = chunk["data"]["__interrupt__"][0].value
        initial_input = Command(resume=get_user_input(interrupt_info))   # 下一轮 invoke 用
        break
```

## 4. 持久化总结：两大组件全能力

### 4.1 checkpoint vs store

| 组件 | 存什么 | 关键标识 | 生命周期 | 核心能力 |
| --- | --- | --- | --- | --- |
| Checkpoint（检查点） | 每个超级步的状态快照、下一步节点、元数据 | `thread_id` + `checkpoint_id` | 会话级 | 断点续跑、重放、时间旅行、HITL |
| Store（存储） | 跨会话业务数据 | `namespace` | 全局级 | 跨线程共享、语义检索 |

六项能力一张清单：状态查询（`get_state`）、历史查询（`get_state_history`）、从指定 checkpoint 恢复（传它的 config）、状态修改（`update_state`，day16 的分支就靠它）、跨会话共享（Store）、故障恢复（从最近成功检查点续跑）。

### 4.2 从检查点重放（最小例子）

```python
history = list(graph.get_state_history(config))                 # 倒序，最新在前
snapshot = next(s for s in history if s.values["step"] == 1)    # 找 step1 执行后的快照
replay_config = {"configurable": {"thread_id": "counter_thread_1",
                                  "checkpoint_id": snapshot.config["configurable"]["checkpoint_id"]}}
graph.invoke(None, replay_config)                               # 传 None = 从该检查点往后继续
```

`invoke(None, config)` 是贯穿 day15/day16 的重要手势：**「不给新输入，从检查点继续」**——断点续跑、重放、恢复中断都用它。

### 4.3 静态断点 interrupt_before

除了动态的 `interrupt()`，还有编译期的静态断点：

```python
graph = builder.compile(checkpointer=memory, interrupt_before=["pay"])
```

执行到 `pay` 节点前自动停住，之后用 `graph.get_state(config).next` 看下一步、`graph.update_state(...)` 批准、再 `graph.invoke(None, config)` 继续。适合「流程固定、就在某节点前必须停」的审批场景；想停在哪一行代码里，还是用 `interrupt()`。

## 5. 踩坑与要点

- **所有高级能力的前提是 checkpointer**：没配就 `interrupt` 不了、崩了也续不上。
- `check_same_thread=False` 是 SQLite + 流式/多线程的必备参数。
- Redis/MySQL/Mongo 的 saver 和 store 都别忘了 `setup()`；SqliteSaver 没有 setup。
- thread_id 要从父图透传到子图，否则子图「记不住」。
- `interrupt()` 所在节点恢复时**整体重跑**，副作用要幂等，这是最反直觉的一条。
- 修剪（trim）和删除会真的丢信息，用户问「我最开始说的名字」时就会答不出；要保信息用总结方案。
- `delete_thread` 之后时间旅行能力一并消失，测试时注意别把想回放的线程删了。
- `update_state` 是「在检查点上新建一个分支」，不改原历史——这点 day16 展开讲。
- 中断 payload 里塞大对象会让检查点膨胀，只传必要信息。

## 6. 关键知识清单

- 短期记忆 = checkpointer + `thread_id`（会话维度）；长期记忆 = store + `user_id/namespace`（用户维度）。
- Saver 家族：InMemory（调试）/ Sqlite（本地）/ Redis / PyMySQL / Mongo；Store 同理，两个都要 `setup()`（Sqlite 除外）。
- 长期记忆通过 `Runtime` 注入：`runtime.context`（自定义 Context）+ `runtime.store`（put/search），`context_schema` 声明。
- 上下文管理四招：trim_messages 裁剪、RemoveMessage 删除、langmem 总结、检查点运维；信息保留与成本之间的取舍。
- 中断三件套：`interrupt(payload)` 暂停、`__interrupt__` 查看、`Command(resume=…)` 恢复；恢复=节点重跑。
- 六条铁律：不 catch、顺序稳、值可序列化、副作用幂等、thread_id 一致、子图内代码会重跑。
- 持久化两大件：checkpoint（会话快照，支持重放/时间旅行/HITL）与 store（跨会话数据）。
- `invoke(None, config)` = 从检查点继续；`interrupt_before=[…]` = 静态断点。
