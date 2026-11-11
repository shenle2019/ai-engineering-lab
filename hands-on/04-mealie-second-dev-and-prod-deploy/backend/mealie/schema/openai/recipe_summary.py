from typing import Literal

from pydantic import Field

from ._base import OpenAIBase


class OpenAIRecipeSummary(OpenAIBase):
    summary: str = Field(
        ...,
        description="A concise overview (2-4 sentences) of what the recipe is, who it suits, and what makes it distinctive.",
    )

    difficulty: Literal["easy", "medium", "hard", "unknown"] = Field(
        ...,
        description=(
            "How hard the recipe is for a home cook. Use 'easy' for few steps and basic techniques, "
            "'medium' for multiple stages or some technique, 'hard' for advanced technique or tight timing, "
            "and 'unknown' when the recipe data is too incomplete to judge."
        ),
    )

    estimated_time: str = Field(
        ...,
        description="Human readable total time from start to finish, e.g. 'about 45 minutes'. Include prep and cook time.",
    )

    highlights: list[str] = Field(
        default_factory=list,
        description="2-5 short bullet points describing what makes this recipe worth cooking (flavor, technique, make-ahead, etc.).",
    )

    warnings: list[str] = Field(
        default_factory=list,
        description=(
            "0-5 short bullet points about things a cook should watch out for, such as missing data, "
            "unusual ingredients, allergens, or steps that are easy to get wrong. Empty when there is nothing to flag."
        ),
    )
