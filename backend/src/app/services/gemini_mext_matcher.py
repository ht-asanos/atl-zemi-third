"""Gemini を用いた MEXT 食品マッチングサービス。

trigram で confidence < 0.6 の食材を候補リストから Gemini に選ばせる。
候補は DB 実在が保証されるため、幻覚リスクなし。
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from app.config import settings
from google import genai

logger = logging.getLogger(__name__)

MODEL = "gemini-3.1-flash-lite-preview"
MAX_RETRIES = 3
GEMINI_MATCH_CONFIDENCE = 0.65  # 保守的に開始。manual_review 境界に近い
BATCH_SIZE = 30
GEMINI_CALL_INTERVAL = 0.5  # 秒。レート制限対策

_PROMPT = """\
あなたは日本の食品成分データベース（文部科学省 食品成分表）のエキスパートです。
レシピの食材名に最も適合するMEXT食品を候補リストから選んでください。

ルール:
- 各食材について、候補リストから最も適切なものを1つ選ぶ
- 該当する候補がない場合は selected_id を "none" にする
- 調理法（生、ゆで、焼き等）が食材名から推測できる場合はそれに合う候補を優先
- 「チキン」→「にわとり」、「ポーク」→「ぶた」など外来語と和名の対応を考慮
- 確信が低い場合も "none" にする（誤マッチより未マッチが安全）

入力: JSON配列 [{"name": "食材名", "candidates": [{"id": "uuid", "name": "MEXT名"}]}]
出力: 同じ長さのJSON配列 [{"selected_id": "uuid" | "none", "reason": "短い理由"}]
JSON配列のみ返す。\
"""


@dataclass
class GeminiMatchResult:
    ingredient_name: str
    mext_food_id: str | None  # UUID string
    mext_food_name: str | None
    confidence: float  # GEMINI_MATCH_CONFIDENCE (0.65) if matched, 0.0 if none


def _extract_json_array(text: str) -> list[dict[str, Any]] | None:
    """```json フェンスまたは裸の JSON 配列を抽出してパースする。"""
    # ```json ... ``` フェンスを除去
    text = re.sub(r"```(?:json)?\s*", "", text).replace("```", "")
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return None
    try:
        obj = json.loads(match.group())
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, list):
        return None
    return obj


def _empty_results(items: list[tuple[str, list[dict[str, Any]]]]) -> list[GeminiMatchResult]:
    return [
        GeminiMatchResult(ingredient_name=name, mext_food_id=None, mext_food_name=None, confidence=0.0)
        for name, _ in items
    ]


async def _call_gemini_batch(
    client: genai.Client,
    items: list[tuple[str, list[dict[str, Any]]]],
) -> list[GeminiMatchResult]:
    """1バッチ分の Gemini API 呼び出し。リトライ付き。"""
    input_data = [{"name": name, "candidates": candidates} for name, candidates in items]

    # 候補 ID セット（幻覚 ID 検出用）
    valid_ids: list[set[str]] = [{c["id"] for c in candidates} for _, candidates in items]

    # ID → name マップ（selected_id の名前解決用）
    id_to_name: list[dict[str, str]] = [{c["id"]: c["name"] for c in candidates} for _, candidates in items]

    input_json = json.dumps(input_data, ensure_ascii=False)
    content = f"{_PROMPT}\n\n入力: {input_json}\n出力:"

    for attempt in range(MAX_RETRIES):
        try:
            response = await client.aio.models.generate_content(
                model=MODEL,
                contents=content,
            )
            text = response.text or ""
            parsed = _extract_json_array(text)

            if parsed is None:
                logger.warning("Gemini response has no JSON array (attempt %d): %s", attempt + 1, text[:200])
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(2**attempt)
                    continue
                return _empty_results(items)

            if len(parsed) != len(items):
                logger.warning(
                    "Gemini response length mismatch: expected %d, got %d",
                    len(items),
                    len(parsed),
                )
                return _empty_results(items)

            results: list[GeminiMatchResult] = []
            for d, (name, _), valid, i2n in zip(parsed, items, valid_ids, id_to_name, strict=True):
                selected_id = str(d.get("selected_id") or "none").strip()
                if selected_id == "none" or selected_id not in valid:
                    results.append(
                        GeminiMatchResult(
                            ingredient_name=name,
                            mext_food_id=None,
                            mext_food_name=None,
                            confidence=0.0,
                        )
                    )
                else:
                    results.append(
                        GeminiMatchResult(
                            ingredient_name=name,
                            mext_food_id=selected_id,
                            mext_food_name=i2n.get(selected_id),
                            confidence=GEMINI_MATCH_CONFIDENCE,
                        )
                    )
            return results

        except json.JSONDecodeError:
            logger.warning("Gemini response JSON parse failed (attempt %d)", attempt + 1)
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(2**attempt)
                continue
            return _empty_results(items)
        except Exception:
            logger.exception("Gemini API call failed (attempt %d)", attempt + 1)
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(2**attempt)
                continue
            return _empty_results(items)

    return _empty_results(items)


async def gemini_match_batch(
    items: list[tuple[str, list[dict[str, Any]]]],  # [(ingredient_name, candidates)]
) -> list[GeminiMatchResult]:
    """複数食材を一括で Gemini マッチング。BATCH_SIZE ごとに API 呼出し。

    API key 未設定時は全て confidence=0.0 を返す（グレースフルデグレード）。
    """
    if not items:
        return []

    if not settings.google_api_key:
        logger.warning("GOOGLE_API_KEY is not set, skipping Gemini MEXT matching")
        return _empty_results(items)

    client = genai.Client(api_key=settings.google_api_key)
    all_results: list[GeminiMatchResult] = []

    for i in range(0, len(items), BATCH_SIZE):
        batch = items[i : i + BATCH_SIZE]
        batch_results = await _call_gemini_batch(client, batch)
        all_results.extend(batch_results)
        if i + BATCH_SIZE < len(items):
            await asyncio.sleep(GEMINI_CALL_INTERVAL)

    return all_results
