"""状态与结构化输出 schema。

状态一律用 TypedDict：LangGraph 只关心「节点返回的 dict 如何合并进状态」，
reducer 决定合并方式（覆盖 / 追加）。
"""
import operator
from dataclasses import dataclass
from typing import Annotated, Literal, TypedDict

from pydantic import BaseModel, Field


class TravelRequest(TypedDict):
    city: str
    days: int
    budget: float
    preference: str


class TravelState(TypedDict, total=False):
    """行程管家的全量状态。total=False 让冷启动只需提供 request。"""

    request: TravelRequest          # 用户请求
    profile: str                     # 长期记忆里的用户画像
    attractions: str                 # 景点规划文案
    foods: str                       # 美食规划文案
    attraction_cost: float           # 景点费用
    food_cost: float                 # 美食费用
    total_cost: float                # 合计
    round: int                       # 已优化轮次
    level: str                       # 消费档位：standard / frugal
    daily_plans: Annotated[list[str], operator.add]   # 子图产出的逐日细则
    feedback: str                    # 评估者给的改进意见
    approved: bool                   # 人工审批结果
    final_plan: str                  # 最终方案
    trace: Annotated[list[str], operator.add]   # 执行轨迹：追加而非覆盖


@dataclass
class UserContext:
    """长期记忆的命名空间来源，跟 thread_id 解耦。

    user_id 必须带默认值：走 HTTP 服务时不传 context，框架会拿空 dict 去构造
    context_schema，没有默认值就直接 TypeError。
    """

    user_id: str = "demo-user"


class Section(BaseModel):
    """编排者-工作者模式里的章节描述。"""

    name: str = Field(description="章节名称")
    description: str = Field(description="该章节要覆盖的内容要点")


class Sections(BaseModel):
    sections: list[Section] = Field(description="报告的完整章节清单")


class Verdict(BaseModel):
    """评估者-优化器模式里的结构化评估结果。"""

    passed: bool = Field(description="是否已经可以交付")
    feedback: str = Field(description="不通过时给出的具体改进意见")


Topic = Literal["history", "food", "nature"]


class TopicChoice(BaseModel):
    """路由模式的结构化输出。

    坑：直接拿 Literal 当 schema 传给 with_structured_output(method="function_calling")
    会报 `Literal[...] is not a module, class, method, or function`——function calling 需要
    可转成函数签名的对象。包一层 BaseModel 就正常了。
    """

    topic: Topic = Field(description="问题归属的话题分类")
