"""楽天レシピ取り込み時の品質ゲート。

主目的:
- 「つゆ・たれ・だし」など単体で食事として成立しないレシピの流入を防ぐ。

方針:
- Gemini による判定を使う。
- 判定失敗時は安全側（除外）に倒す。
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from app.config import settings
from google import genai

logger = logging.getLogger(__name__)

MODEL = "gemini-3.1-flash-lite-preview"
MAX_RETRIES = 3
DEFAULT_BATCH_SIZE = 40

_PROMPT = """\
あなたは料理レシピ品質判定のアシスタントです。
与えられたレシピが「単体で1食の料理として成立するか」を判定してください。

判定ルール:
- is_meal=true:
  主菜/主食/副菜/汁物など、単体で献立の1品として成立する料理。
  例: 鍋焼きうどん、焼きうどん、カレーうどん、肉うどん、ナポリタン、
      親子丼、チャーハン、味噌汁、豚汁、肉じゃが、野菜炒め、つゆだく牛丼

- is_meal=false (以下は全て除外):
  1. つゆ・たれ・ソース・ドレッシング・調味料レシピ全般
     例: つけつゆ、つけ汁、めんつゆの作り方、だし汁、つけだれ、かえし、
         パスタソース、トマトソース、ドレッシング、マヨソース、タルタルソース
  2. 薬味・トッピング・ふりかけ単体
     例: 薬味ねぎ、大根おろし、天かす、ふりかけ、佃煮
  3. 具材だけのレシピ（完成した料理ではないもの）
     例: 「うどんの具」「トッピング3種」「パスタの具材」
  4. レシピ集・まとめ系
     例: 「レシピ3選」「まとめ」「アレンジ5選」「○○の作り方集」
  5. 調理テクニック・下ごしらえ系
     例: 「だしの取り方」「野菜の切り方」「下味の付け方」

重要な判断基準:
- タレ/つゆ/ソース/ドレッシング/調味料レシピは全て is_meal=false
- 「ざるうどんのつけつゆ」「うどんのたれ」「パスタのソース」→ is_meal=false
- 「鍋焼きうどん」「焼きうどん」「カレーパスタ」→ is_meal=true
- タイトルに「つゆ」「たれ」を含むが料理名の一部（例: 「つゆだく牛丼」）→ is_meal=true
- 材料が調味料のみ（醤油、みりん、酢、砂糖等）→ is_meal=false の可能性大

出力形式:
入力配列と同じ長さの JSON 配列のみを返す。
各要素は {"is_meal": true|false, "reason": "短い理由"}。
余計な説明文は書かない。\
"""


@dataclass
class RecipeQualityGateResult:
    accepted: list[dict[str, Any]] = field(default_factory=list)
    rejected: list[dict[str, Any]] = field(default_factory=list)  # {"recipe": dict, "reason": str}


def _build_inputs(recipes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """判定に必要な最小限情報へ圧縮する。"""
    payload: list[dict[str, Any]] = []
    for r in recipes:
        mats = r.get("ingredients") or []
        ingredient_names = []
        for x in mats[:8]:
            if isinstance(x, dict):
                name = x.get("ingredient_name")
                if name:
                    ingredient_names.append(str(name))
            elif isinstance(x, str):
                ingredient_names.append(x)
        payload.append(
            {
                "title": r.get("title", ""),
                "description": r.get("description", ""),
                "category": (r.get("tags") or [""])[0] if (r.get("tags") or []) else "",
                "ingredients": ingredient_names,
            }
        )
    return payload


def _extract_json_array(text: str) -> list[dict[str, Any]] | None:
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return None
    try:
        obj = json.loads(match.group())
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, list):
        return None
    out: list[dict[str, Any]] = []
    for item in obj:
        if not isinstance(item, dict):
            return None
        out.append(item)
    return out


async def _call_gemini(client: genai.Client, batch_inputs: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
    content = f"{_PROMPT}\n\n入力:\n{json.dumps(batch_inputs, ensure_ascii=False)}\n\n出力:"
    for attempt in range(MAX_RETRIES):
        try:
            resp = await client.aio.models.generate_content(model=MODEL, contents=content)
            parsed = _extract_json_array(resp.text or "")
            if parsed is None:
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(2**attempt)
                    continue
                return None
            return parsed
        except Exception:
            logger.exception("recipe quality gate gemini call failed (attempt=%d)", attempt + 1)
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(2**attempt)
                continue
            return None
    return None


def _partition_with_decisions(
    recipes: list[dict[str, Any]],
    decisions: list[dict[str, Any]] | None,
    fallback_reason: str,
) -> RecipeQualityGateResult:
    result = RecipeQualityGateResult()
    if decisions is None or len(decisions) != len(recipes):
        for r in recipes:
            result.rejected.append({"recipe": r, "reason": fallback_reason})
        return result

    for recipe, d in zip(recipes, decisions, strict=True):
        is_meal = d.get("is_meal") is True
        reason = str(d.get("reason") or "")
        if is_meal:
            result.accepted.append(recipe)
        else:
            result.rejected.append({"recipe": recipe, "reason": reason or "not_meal_like"})
    return result


async def filter_meal_like_recipes(
    recipes: list[dict[str, Any]],
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> RecipeQualityGateResult:
    """LLMで「食事として成立するレシピ」のみを残す。

    API keyなし時は安全側（全reject）に倒す。楽天取込経路で使用。
    YouTube/admin 経路は filter_meal_like_recipes_safe() を使うこと。
    """
    if not recipes:
        return RecipeQualityGateResult()
    if not settings.google_api_key:
        return _partition_with_decisions(recipes, None, "missing_google_api_key")

    client = genai.Client(api_key=settings.google_api_key)
    final = RecipeQualityGateResult()

    for i in range(0, len(recipes), batch_size):
        batch = recipes[i : i + batch_size]
        batch_inputs = _build_inputs(batch)
        decisions = await _call_gemini(client, batch_inputs)
        part = _partition_with_decisions(batch, decisions, "llm_decision_failed")
        final.accepted.extend(part.accepted)
        final.rejected.extend(part.rejected)

    return final


async def filter_meal_like_recipes_safe(
    recipes: list[dict[str, Any]],
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> RecipeQualityGateResult:
    """Gemini 判定。API keyなし時は全 accept にフォールバック（既存フィルタに委譲）。

    YouTube/admin 取込経路用。keyなし時にブロックしない設計。
    楽天取込経路は filter_meal_like_recipes() を使うこと（keyなし → 全reject）。
    """
    if not recipes:
        return RecipeQualityGateResult()
    if not settings.google_api_key:
        logger.warning(
            "GOOGLE_API_KEY not set — quality gate skipped, accepting all %d recipes",
            len(recipes),
        )
        return RecipeQualityGateResult(accepted=list(recipes))

    return await filter_meal_like_recipes(recipes, batch_size=batch_size)
