"""AI でレシピ手順を生成するサービス。"""

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

from app.config import settings
from app.models.recipe import Recipe, RecipeStep
from google import genai

from supabase import AsyncClient

logger = logging.getLogger(__name__)

MODEL = "gemini-3.1-flash-lite-preview"
MODEL_VERSION = f"gemini:{MODEL}:v1"

PROMPT = """\
あなたは家庭料理の調理手順を作るアシスタントです。
与えられたレシピ情報から、実際に作れる手順を日本語で作成してください。

制約:
- 4〜8ステップ
- 各ステップは100文字以内
- 曖昧な表現を避け、動詞で始める
- 火加減・時間の目安が分かるなら含める
- 返答は必ず JSON 配列のみ
  形式: [{"step_no":1,"text":"...","est_minutes":5|null}, ...]
"""


def _build_input(recipe: Recipe) -> str:
    ingredients = [
        f"- {i.ingredient_name}" + (f" ({i.amount_text})" if i.amount_text else "") for i in recipe.ingredients
    ]
    lines = [
        f"タイトル: {recipe.title}",
        f"説明: {recipe.description or ''}",
        f"人数: {recipe.servings}人前",
        f"調理時間: {recipe.cooking_minutes or '不明'}分",
        "材料:",
        *ingredients,
    ]
    return "\n".join(lines)


def _extract_json_array(text: str) -> list[dict[str, Any]] | None:
    m = re.search(r"\[[\s\S]*\]", text)
    if not m:
        return None
    try:
        value = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(value, list):
        return None
    return [v for v in value if isinstance(v, dict)]


def _sanitize_steps(raw_steps: list[dict[str, Any]]) -> list[RecipeStep]:
    steps: list[RecipeStep] = []
    for idx, row in enumerate(raw_steps, start=1):
        text = str(row.get("text", "")).strip()
        if not text:
            continue
        est_minutes = row.get("est_minutes")
        if not isinstance(est_minutes, int):
            est_minutes = None
        steps.append(
            RecipeStep(
                step_no=int(row.get("step_no", idx)),
                text=text[:100],
                est_minutes=est_minutes,
            )
        )
    return steps[:8]


async def generate_steps_for_recipe(recipe: Recipe) -> list[RecipeStep]:
    """レシピから AI 手順を生成する。失敗時は空配列。"""
    if not settings.google_api_key:
        return []
    if not recipe.ingredients:
        return []

    client = genai.Client(api_key=settings.google_api_key)
    payload = f"{PROMPT}\n\n入力:\n{_build_input(recipe)}\n\n出力:"
    try:
        resp = await client.aio.models.generate_content(model=MODEL, contents=payload)
        data = _extract_json_array(resp.text or "")
        if not data:
            return []
        return _sanitize_steps(data)
    except Exception:
        logger.exception("failed to generate recipe steps: recipe_id=%s", recipe.id)
        return []


async def ensure_generated_steps(supabase: AsyncClient, recipe: Recipe) -> Recipe:
    """手順が未生成なら生成してDB保存し、Recipeに反映して返す。"""
    if recipe.generated_steps:
        recipe.steps_status = "generated"
        return recipe
    if not settings.google_api_key:
        recipe.steps_status = "pending"
        return recipe

    steps = await generate_steps_for_recipe(recipe)
    if steps:
        payload = [s.model_dump() for s in steps]
        try:
            await (
                supabase.table("recipes")
                .update(
                    {
                        "generated_steps": payload,
                        "steps_status": "generated",
                        "steps_model_version": MODEL_VERSION,
                        "steps_generated_at": datetime.now(UTC).isoformat(),
                    }
                )
                .eq("id", str(recipe.id))
                .execute()
            )
        except Exception:
            # マイグレーション未適用環境でも詳細表示自体は継続させる
            logger.exception("failed to persist generated steps: recipe_id=%s", recipe.id)
        recipe.generated_steps = steps
        recipe.steps_status = "generated"
        return recipe

    try:
        await supabase.table("recipes").update({"steps_status": "failed"}).eq("id", str(recipe.id)).execute()
    except Exception:
        logger.exception("failed to persist steps_status=failed: recipe_id=%s", recipe.id)
    recipe.steps_status = "failed"
    return recipe
