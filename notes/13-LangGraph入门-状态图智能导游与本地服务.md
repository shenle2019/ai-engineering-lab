# LangGraph 入门：状态图、智能导游案例与本地服务

> 来源：python 山顶会三期 day13（LangGraph 之智能导游案例 / 本地服务等），课件 `day17-课堂笔记.md` + 代码包（`LangGraph_demo`、`langgraph_demo001`、`langgraph_demo02-空项目`）
> 定位：理解向笔记，记录机制、要点与踩坑，不复刻课件代码

## 0. 这份内容在讲什么

day13 是 LangGraph 的第一次课，把「用代码画流程图的方式编排 LLM 应用」这件事讲透：

```
LangGraph 是什么   → 状态机 / 流程图式编程框架，LangChain 的新一代
第一个完整案例     → 智能导游：生成计划 → 预算审核 → 超支重规划（带循环的工作流）
两套写图 API       → Graph API（六步）/ Functional API（四步）
工程化落地         → 目录结构、langgraph new / dev、SDK 客户端调用、LangSmith 部署
最后一个判断题     → 工作流 vs 智能体：不是越自主越好
```

一条主线：**State 是图的血液，节点是函数，边是流程控制，编译（compile）之后图就变成一个可 invoke / stream 的对象。** 后续 day14–day16 的所有高级能力（子图、记忆、中断、时间旅行、持久执行）都建在这个心智模型上。

## 1. LangGraph 是什么

课件给的定位：**用「流程图 / 状态机」的方式，搭建可控、可循环、可回溯的 LLM 应用**。如果用过 Coze 的拖拽式智能体，LangGraph 就是「用代码画那朵画」。

和 LangChain 的对比，课件用了一个很形象的说法：

| | LangChain | LangGraph |
| --- | --- | --- |
| 形态 | 链条（Chain），A → B → C → D | 图（Graph），可分支、循环、跳转、重试、并行 |
| 比喻 | 自动售货机：投币 → 选货 → 出货，流程固定不能回头 | 餐厅点菜：问菜 → 推荐 → 查库存 → 没有就换 → 不好吃重做 → 满意结账 |
| 适合 | 简单 RAG、单轮问答、固定步骤小应用 | 复杂 Agent、多轮对话、企业级工作流 |

它比 LangChain 多出来的六件事：流程完全可控、支持条件分支、支持循环/重试/反思（真正 Agent 的基础）、内置状态管理（State）、可回溯可调试可恢复、天然适合多智能体。

课件列出的整门课知识点清单，正好是后面几天的目录：安装 → 快速开始（图 API / 函数 API）→ 应用程序结构 → LangSmith 部署 → 本地运行 → 工作流与智能体 → 持久化 → 持久执行 → 流式处理 → 中断 → 时间旅行 → 内存 → 子图。

## 2. 第一个完整案例：智能导游

### 2.1 需求与状态设计

用户输入城市、预算、天数、偏好，生成旅行计划；**预算超了要自动重新规划，直到通过**。这是 LangChain 那种单向链条做不到的——它需要「往回走」的边。

第一步永远是定 State。课件用 `TypedDict` 描述整张图运行过程中需要的所有变量：

```python
class TravelPlanState(TypedDict):
    city: str
    days: int
    budget: float
    user_preference: str
    attraction_plan: str
    food_plan: str
    total_cost: float
    is_budget_ok: bool      # 预算审核结果，条件边要用
    final_plan: str
    conversation_history: list
```

判断标准很简单：**整个流程图运行中会用到的变量，全放进去**。节点函数通过 `state["xxx"]` 读，通过返回 dict 写（只返回要更新的字段，LangGraph 负责合并）。

### 2.2 节点 = 普通函数

六个节点：获取偏好 → 景点规划 → 美食规划 → 预算审核 → 重新规划 → 生成最终方案。每个节点的模式都一样：

```python
def plan_attractions(state: TravelPlanState):
    prompt = f"请为用户规划{state['city']} {state['days']}天的景点行程……"
    content = llm.invoke([HumanMessage(content=prompt)]).content
    # 约定输出格式，把「规划文本」和「总费用」拆开
    plan_part = content.split("景点总费用：")[0]
    attraction_cost = extract_numeric_value(content.split("景点总费用：")[1])
    return {"attraction_plan": plan_part, "total_cost": attraction_cost}
```

课件里有两个值得抄走的小工具：
- `extract_numeric_value()`：用正则 `\d+\.?\d*` 抓**最后一个**数字，兜住模型输出里的「约 800 元」「800+200」这类脏数据；
- `validate_numeric_input()`：天数 1–30、预算 ≥100 的输入校验。

费用汇总发生在 `plan_food` 里（`state["total_cost"] + food_cost`），审核在 `check_budget` 里做纯 Python 比较——**能不用 LLM 判断的地方就不用**，省钱且稳定。

### 2.3 连边：循环就靠这一条回边

```python
graph = StateGraph(TravelPlanState)
graph.add_node("get_user_preference", get_user_preference)
# ……
graph.set_entry_point("get_user_preference")
graph.add_edge("get_user_preference", "plan_attractions")
graph.add_edge("plan_attractions", "plan_food")
graph.add_edge("plan_food", "check_budget")
graph.add_conditional_edges("check_budget", budget_check_branch)  # 达标 → 最终方案；超支 → 重规划
graph.add_edge("re_plan", "check_budget")                        # 回边：重规划后重新审核
graph.add_edge("generate_final_plan", END)
travel_graph = graph.compile()
```

条件边函数只返回**下一个节点的名字**：

```python
def budget_check_branch(state):
    return "generate_final_plan" if state["is_budget_ok"] else "re_plan"
```

`re_plan → check_budget` 这条回边就是循环的全部秘密。另外 `graph.set_entry_point()` 与 `add_edge(START, ...)` 等价，后者在后续课程里更常用。

### 2.4 看见流程图：两种方式

| 方式 | 说明 | 代价 |
| --- | --- | --- |
| graphviz 手绘彩色图 | `Digraph` 手动加 node/edge，可自定义形状颜色、中文标签 | 代码多，和真实图可能不同步 |
| LangGraph 内置 mermaid | `agent.get_graph(xray=True).draw_mermaid_png()` 按节点和连线自动生成 | 几行代码，黑白色 |

graphviz 需要先装**系统软件**（`dot --version` 验证，Windows 有安装版和免安装版），再 `pip install graphviz`。内置方式是调 mermaid 在线服务渲染，**断网时会失败**——这是课件环境下常见的一个坑。

## 3. 两套 API：Graph API 与 Functional API

### 3.1 Graph API：六步建一个 ReAct Agent

课件用「加减乘除计算器 Agent」演示，六步固定套路：

| 步骤 | 内容 |
| --- | --- |
| 1 | 定义模型和工具（`ChatOpenAI` + `@tool` + `bind_tools`） |
| 2 | 定义状态（`MessagesState` 自定义版） |
| 3 | 定义模型节点 `llm_call` |
| 4 | 定义工具节点 `tool_node` |
| 5 | 定义结束逻辑 `should_continue` |
| 6 | 构建并编译 |

两个关键细节：

```python
class MessagesState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]  # reducer：新消息追加而不是覆盖
    llm_calls: int                                       # 统计模型被调次数
```

`Annotated[..., operator.add]` 是 LangGraph 的 reducer 机制：节点返回的列表会**拼接**进旧值而不是替换。所有多轮对话场景都靠它。

```python
def should_continue(state) -> Literal["tool_node", END]:
    return "tool_node" if state["messages"][-1].tool_calls else END

builder.add_conditional_edges("llm_call", should_continue, ["tool_node", END])
builder.add_edge("tool_node", "llm_call")   # 工具结果回到模型 → 这就是 ReAct 循环
```

经典 ReAct 轨迹：用户问 → 模型思考要调工具 → tool_node 执行 → 结果回给模型 → 模型决定收尾 → END。

### 3.2 Functional API：四步，用 @task / @entrypoint

不想画图就写「带检查点的函数」：

```python
from langgraph.func import entrypoint, task

@task                              # 相当于一个节点
def call_llm(messages): ...

@task
def call_tool(tool_call): ...

@entrypoint()                      # 相当于整张图
def agent(messages):
    model_response = call_llm(messages).result()   # task 调用返回 future，.result() 取值
    while model_response.tool_calls:
        tool_results = [call_tool(tc).result() for tc in model_response.tool_calls]
        messages = add_messages(messages, [model_response, *tool_results])
        model_response = call_llm(messages).result()
    return add_messages(messages, model_response)
```

对比一眼就能明白：Graph API 显式声明节点和边、结构可画图；Functional API 就是普通 Python 控制流（while / if），靠装饰器让框架接管状态与检查点。**流程线性、逻辑复杂时 Functional 更顺手；要可视化、要分支聚合时 Graph 更清晰。**

## 4. 工程化：目录结构与本地服务

单个 py 文件不适合工程化，官方给了标准结构：

```
项目名/
├── my_agent/                 # 代码都写在这里
│   ├── utils/
│   │   ├── tools.py          # 工具
│   │   ├── nodes.py          # 节点
│   │   └── state.py          # 状态
│   ├── __init__.py
│   └── agent.py              # graph = graph.compile() 放这里
├── .env
├── requirements.txt          # 或 pyproject.toml（uv / pip install -e .）
└── langgraph.json            # 配置文件
```

`langgraph.json` 是部署契约：声明依赖、从哪个文件加载哪个变量、环境变量文件：

```json
{
  "dependencies": ["langchain_openai", "./your_package"],
  "graphs": { "my_agent": "./your_package/your_file.py:agent" },
  "env": "./.env"
}
```

脚手架三连：

```bash
pip install "langgraph-cli[inmem]"     # 需要 Python ≥ 3.11
langgraph new langgraph_demo001        # 从模板拉项目（国内可能拉 GitHub 失败，可重试/用课件空项目）
pip install -e .                       # 在虚拟环境里装依赖
langgraph dev                          # 本地起 Agent 服务器，默认 127.0.0.1:2024
```

`langgraph dev` 起来后提供 REST/SSE 接口，自带 Studio 调试页面（可选注册 LangSmith）。把练习改成项目形式时，`agent.py` 里必须有一个**模块级编译好的 `graph` 变量**，`langgraph.json` 才能找到它。

常见坑：PyCharm 里 `from agent.state import ...` 报红，本质是没把 `src`（项目根）标成 Sources Root，代码本身没问题。

## 5. 客户端调用：langgraph-sdk

服务起来后，客户端两行接上：

```python
# 同步
from langgraph_sdk import get_sync_client
client = get_sync_client(url="http://localhost:2024")
for chunk in client.runs.stream(None, "agent", input={"messages": [{"role": "human", "content": "add 4 and 4"}]}, stream_mode="messages-tuple"):
    print(chunk.event, chunk.data)
```

异步版把 `get_sync_client` 换成 `get_client`、`for` 换成 `async for` 即可。第一个参数传 `None` 表示「无线程运行」，第二个参数是在 `langgraph.json` 里注册的图名。

## 6. LangSmith 部署（了解即可）

官方路线：代码推到 GitHub → LangSmith 后台 New Deployment 关联仓库 → 约 15 分钟构建 → Studio 里测试 → 拿 API URL 调。课件明确说这条「不合适」——**企业里一般部署在自己的云服务器上，对外只暴露 API**。LangSmith 个人单智能体免费，多智能体/企业收费，这也是自建的理由之一。

## 7. 最后一个判断题：工作流 vs 智能体

课件用一张图收尾，核心结论是**按场景选，不要盲目追 Agent**：

| 形态 | 谁在控制流程 | 例子 |
| --- | --- | --- |
| 工作流（Workflow） | 开发者写死的流程，LLM 只在节点里干活 | 智能导游：城市/预算/天数 → 景点 → 美食 → 审核 → 输出 |
| 高级工作流（编排） | 流程主干固定，局部由 LLM 决策（路由、派发） | day14 的路由、编排者-工作者 |
| 智能体（Agent） | LLM 自己决定下一步、调什么工具、循环几次 | 给一个「帮我赚钱」的任务，全由模型拆解执行 |

「LLM 在代码执行过程中有多少控制权」是这三种形态的唯一分界线。控制权越多越灵活，也越贵、越不可预测、越难测试。

## 8. 踩坑与要点

- **graphviz 是系统软件**，不是 pip 包；`dot --version` 不通就是没装或没进 PATH。
- **`draw_mermaid_png()` 依赖网络**（在线渲染），离线环境会挂。
- **State 字段想清楚再动手**：条件边判断用的字段（如 `is_budget_ok`）必须显式落在 State 里，节点之间不共享局部变量。
- 节点**只返回要改的字段**；返回整个 state 不是错，但配合 reducer 时容易重复追加。
- `Annotated[list, operator.add]` 加错位置（加在 State 类上而不是字段上）是最常见的低级错误。
- 结构化费用解析靠 `split("景点总费用：")` 这类**约定格式**，模型不听话时要兜底默认值 0，别让 `IndexError` 炸掉整条图。
- `langgraph new` 要联网拉模板；`langgraph dev` 必须在装了 `langgraph-cli[inmem]` 的环境里跑。
- Functional API 里 `.result()` 不能省——`call_llm(messages)` 返回的是 future。
- 工作流能解决的问题别上 Agent：可控性、成本、可测试性都差一个量级。

## 9. 关键知识清单

- LangGraph = 状态图框架：State（TypedDict）+ 节点（函数）+ 边（add_edge / add_conditional_edges）+ compile。
- 循环 = 一条回边（`re_plan → check_budget`）；分支 = 条件边函数返回节点名。
- 两种可视化：graphviz 手绘（彩色、代码多）、`get_graph().draw_mermaid_png()`（自动、黑白、需联网）。
- Graph API 六步：模型工具 → State → 模型节点 → 工具节点 → 结束判断 → 编译；ReAct 循环 = `tool_node → llm_call` 回边。
- Functional API 四步：`@task` 节点 + `@entrypoint` 图，普通 Python 控制流。
- reducer：`Annotated[list, operator.add]` 让消息列表追加而非覆盖。
- 工程结构：`my_agent/utils/{tools,nodes,state}.py` + `agent.py`（导出 graph）+ `langgraph.json`。
- 本地服务：`langgraph new` → `pip install -e .` → `langgraph dev`（2024 端口）→ SDK `runs.stream`。
- 工作流 / 高级编排 / Agent 的分界线是 LLM 的控制权大小，按场景选型。
