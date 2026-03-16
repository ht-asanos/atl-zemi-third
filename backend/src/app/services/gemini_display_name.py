"""Gemini を使って MEXT 食品名から短い表示名を生成するサービス。"""

import asyncio
import json
import logging
import re

from app.config import settings
from google import genai

logger = logging.getLogger(__name__)

MODEL = "gemini-3.1-flash-lite-preview"

PROMPT = """\
あなたはレシピサイトの食材名エキスパートです。
MEXT食品成分データベースの正式名称から、レシピサイトで使われる自然で短い食材名を抽出してください。

ルール:
- カテゴリ階層（"穀類/", "調味料及び香辛料類/"等）は除去
- "- 01.一般成分表..." のような末尾の表番号は除去
- 調理法の詳細は省略（ただし「生」「ゆで」など重要な区別は残す）
- 日本のレシピサイトで最も一般的に使われる名前にする

入力: JSON配列
出力: 同じ長さのJSON配列（短い表示名のみ）

例:
入力: ["調味料及び香辛料類/＜調味料類＞/マヨネーズタイプ調味料/低カロリータイプ", "肉類/＜鶏肉＞/もも/皮つき/生"]
出力: ["マヨネーズ（低カロリー）", "鶏もも肉"]
"""

FORBIDDEN = ["/", "一般成分表", "無機質", "ビタミン類", "- 01.", "- 02."]

MAX_RETRIES = 3


def _validate_display_name(raw: str, original: str) -> str | None:
    """LLM出力を検証する。不合格なら None を返す。"""
    name = raw.strip()
    # 全角/半角空白の正規化
    name = re.sub(r"\s+", " ", name)
    # 長さチェック: 1〜40文字
    if not (1 <= len(name) <= 40):
        return None
    # 禁止パターン: 階層パスや表番号の残留
    if any(p in name for p in FORBIDDEN):
        return None
    # 元名と完全一致（短縮されていない）→ None
    if name == original:
        return None
    return name


async def _call_gemini(client: genai.Client, names: list[str]) -> list[str | None]:
    """Gemini API を呼び出して表示名を取得する。リトライ付き。"""
    input_json = json.dumps(names, ensure_ascii=False)
    content = f"{PROMPT}\n\n入力: {input_json}\n出力:"

    for attempt in range(MAX_RETRIES):
        try:
            response = await client.aio.models.generate_content(
                model=MODEL,
                contents=content,
            )
            text = response.text or ""
            # JSON配列を抽出（前後のテキストを除去）
            match = re.search(r"\[.*\]", text, re.DOTALL)
            if not match:
                logger.warning("Gemini response has no JSON array (attempt %d): %s", attempt + 1, text[:200])
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(2**attempt)
                    continue
                return [None] * len(names)

            parsed = json.loads(match.group())
            if not isinstance(parsed, list) or len(parsed) != len(names):
                logger.warning(
                    "Gemini response array length mismatch: expected %d, got %d",
                    len(names),
                    len(parsed) if isinstance(parsed, list) else -1,
                )
                return [None] * len(names)

            # 個別バリデーション
            results: list[str | None] = []
            for raw, original in zip(parsed, names, strict=True):
                if isinstance(raw, str):
                    results.append(_validate_display_name(raw, original))
                else:
                    results.append(None)
            return results

        except json.JSONDecodeError:
            logger.warning("Gemini response JSON parse failed (attempt %d)", attempt + 1)
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(2**attempt)
                continue
            return [None] * len(names)
        except Exception:
            logger.exception("Gemini API call failed (attempt %d)", attempt + 1)
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(2**attempt)
                continue
            return [None] * len(names)

    return [None] * len(names)


async def generate_display_names(raw_names: list[str], batch_size: int = 50) -> list[str | None]:
    """MEXT 正式名称のリストから短い表示名を一括生成する。

    失敗した個別の名前は None を返す（呼び出し側で name にフォールバック）。
    """
    if not raw_names:
        return []

    if not settings.google_api_key:
        logger.error("GOOGLE_API_KEY is not set")
        return [None] * len(raw_names)

    client = genai.Client(api_key=settings.google_api_key)
    all_results: list[str | None] = []

    for i in range(0, len(raw_names), batch_size):
        batch = raw_names[i : i + batch_size]
        batch_results = await _call_gemini(client, batch)
        all_results.extend(batch_results)

    return all_results
