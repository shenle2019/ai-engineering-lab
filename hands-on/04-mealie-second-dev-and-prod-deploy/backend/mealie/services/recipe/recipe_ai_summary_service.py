import json
import re

from mealie.schema.openai.recipe_summary import OpenAIRecipeSummary
from mealie.schema.recipe.recipe import Recipe
from mealie.services._base_service import BaseService
from mealie.services.openai import OpenAIService
from mealie.services.openai.openai import OpenAIDataInjection

# Some OpenAI-compatible providers only support `{"type": "json_object"}` and reject
# `json_schema` structured output. Models occasionally wrap JSON in a markdown fence
# even in JSON mode, so strip it before validation.
RE_JSON_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$")


class RecipeAISummaryService(BaseService):
    """Generate a cooking summary for an existing recipe with the configured AI provider.

    The summary is a read-only projection: nothing is written back to the database.
    """

    def __init__(self, openai_service: OpenAIService | None = None) -> None:
        super().__init__()
        self.openai_service = openai_service or OpenAIService()

    @staticmethod
    def _recipe_payload(recipe: Recipe) -> dict:
        """Trim the recipe down to the fields the model needs.

        Only data the cook can already see is sent. Internal identifiers, image paths,
        ownership information and timestamps are deliberately excluded.
        """
        return {
            "name": recipe.name,
            "description": recipe.description,
            "recipe_yield": recipe.recipe_yield,
            "recipe_servings": recipe.recipe_servings,
            "prep_time": recipe.prep_time,
            "cook_time": recipe.cook_time,
            "total_time": recipe.total_time,
            "tags": [tag.name for tag in recipe.tags or []],
            "categories": [category.name for category in recipe.recipe_category or []],
            "ingredients": [
                ingredient.original_text or ingredient.display or ingredient.note
                for ingredient in recipe.recipe_ingredient
            ],
            "instructions": [step.text for step in recipe.recipe_instructions or []],
        }

    async def generate(self, recipe: Recipe) -> OpenAIRecipeSummary:
        payload = self._recipe_payload(recipe)
        prompt = self.openai_service.get_prompt(
            "recipes.summarize-recipe",
            [
                OpenAIDataInjection(
                    description="Recipe data as JSON",
                    value=json.dumps(payload, ensure_ascii=False, indent=2),
                )
            ],
        )
        message = "Summarize the recipe included above."

        try:
            result = await self.openai_service.get_response(
                prompt,
                message,
                response_schema=OpenAIRecipeSummary,
            )
        except Exception as e:
            if not self._supports_json_mode_fallback(e):
                raise

            self.logger.warning(f"Structured output unavailable, falling back to JSON mode: {e}")
            result = await self._generate_in_json_mode(prompt, message)

        if result is None:
            raise ValueError("The AI service returned an empty summary")

        return result

    @staticmethod
    def _supports_json_mode_fallback(error: Exception) -> bool:
        message = str(error).lower()
        return "response_format" in message or "badrequest" in message

    async def _generate_in_json_mode(self, prompt: str, message: str) -> OpenAIRecipeSummary:
        client = self.openai_service.get_client()
        response = await client.chat.completions.create(
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": message},
            ],
            model=self.openai_service.model,
            response_format={"type": "json_object"},
        )

        if not response.choices:
            raise ValueError("The AI service returned an empty response")

        raw = RE_JSON_FENCE.sub("", response.choices[0].message.content or "")
        return OpenAIRecipeSummary.model_validate_json(raw)
