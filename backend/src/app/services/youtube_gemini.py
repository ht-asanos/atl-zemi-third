"""Gemini によるレシピ抽出・主食適応

Gemini マルチモーダル API を使ったレシピ構造化データの抽出と、
主食指定への再構成を行う。
"""

import asyncio
import json
import logging
import re
from pathlib import Path

from app.config import settings
from app.services.youtube_transcript_service import naturalize_auto_transcript
from google import genai

logger = logging.getLogger(__name__)

# --- Gemini 定数 ---
VIDEO_MODEL = "gemini-2.5-flash"
MAX_RETRIES_GEMINI = 3
GEMINI_RETRY_WAIT = 3.0
GEMINI_TIMEOUT = 45

RECIPE_EXTRACTION_PROMPT = """\
あなたは料理レシピの分析アシスタントです。
この音声は料理レシピの動画です。内容を分析し、以下のJSON形式で抽出してください。

{
  "title": "料理名",
  "servings": 2,
  "cooking_minutes": 15,
  "ingredients": [
    {"ingredient_name": "鶏もも肉", "amount_text": "300g"},
    {"ingredient_name": "醤油", "amount_text": "大さじ2"}
  ],
  "steps": [
    {"step_no": 1, "text": "鶏肉を一口大に切る", "est_minutes": 3}
  ],
  "tags": ["鶏肉", "和食"]
}

ルール:
- ingredient_name は食材名のみ（分量を含めない）
- amount_text は「300g」「大さじ2」「2個」「少々」など日本語の計量表現
- 分量不明なら amount_text を null
- 調味料（塩、こしょう、醤油等）も必ず含める
- JSON のみ出力（説明文不要）
"""

RECIPE_STAPLE_ADAPT_PROMPT_TEMPLATE = """\
あなたは料理レシピの編集アシスタントです。
以下の元レシピを参考に、主食「{staple_name}」に合うレシピへ再構成してください。

出力は次の JSON 形式のみ:
{{
  "title": "料理名",
  "servings": 2,
  "cooking_minutes": 15,
  "ingredients": [
    {{"ingredient_name": "鶏もも肉", "amount_text": "300g"}},
    {{"ingredient_name": "{staple_name}", "amount_text": "1人前"}}
  ],
  "steps": [
    {{"step_no": 1, "text": "下ごしらえ", "est_minutes": 3}}
  ],
  "tags": ["和食", "{staple_name}"]
}}

要件:
- 主食「{staple_name}」を ingredients に必ず含める
- 元レシピの料理意図をなるべく維持する
- ingredient_name は食材名のみ（分量は amount_text）
- steps は 1 件以上
- JSON 以外の文字を出力しない

元レシピ(JSON):
{original_recipe_json}
"""

RECIPE_FROM_TRANSCRIPT_PROMPT_TEMPLATE = """\
あなたは料理動画の文字起こしから、実用的なレシピ情報を抽出するアシスタントです。
以下の文字起こしを解析して、必ず JSON のみで出力してください。

{{
  "title": "料理名",
  "servings": 2,
  "cooking_minutes": 20,
  "ingredients": [
    {{"ingredient_name": "うどん", "amount_text": "2玉"}},
    {{"ingredient_name": "牛肉", "amount_text": "200g"}}
  ],
  "steps": [
    {{"step_no": 1, "text": "下準備をする", "est_minutes": 5}}
  ],
  "tags": ["和食", "うどん"]
}}

抽出ルール:
- ingredient_name は食材名のみ
- amount_text は分量表現（不明なら null）
- steps は 1件以上。時系列で並べる
- 主食「{staple_name}」に合う内容を優先する
- 不明情報は推定せず null にする
- JSON 以外の文は出力しない

動画タイトル:
{video_title}

文字起こし:
{transcript_text}
"""


def _validate_extracted_recipe(data: dict) -> bool:
    """Gemini 抽出結果の最低品質チェック。"""
    title = data.get("title")
    if not title or not isinstance(title, str) or not title.strip():
        return False

    ingredients = data.get("ingredients")
    if not ingredients or not isinstance(ingredients, list) or len(ingredients) == 0:
        return False

    for ing in ingredients:
        name = ing.get("ingredient_name")
        if not name or not isinstance(name, str) or not name.strip():
            return False

    steps = data.get("steps")
    if not steps or not isinstance(steps, list) or len(steps) == 0:
        return False

    for step in steps:
        text = step.get("text")
        if not text or not isinstance(text, str) or not text.strip():
            return False

    return True


def _parse_gemini_json(text: str) -> dict | None:
    """Gemini レスポンスから JSON を抽出してパースする。"""
    # コードブロック内の JSON を抽出
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        text = match.group(1)

    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Failed to parse Gemini JSON response: %s", text[:200])
        return None


def _matches_staple(recipe: dict, staple_name: str) -> bool:
    """主食寄せが成立しているかを軽く検証する。"""
    staple = staple_name.strip()
    if not staple:
        return True

    title = str(recipe.get("title") or "")
    if staple in title:
        return True

    for tag in recipe.get("tags") or []:
        if isinstance(tag, str) and staple in tag:
            return True

    for ing in recipe.get("ingredients") or []:
        name = str((ing or {}).get("ingredient_name") or "")
        if staple in name:
            return True
    return False


async def adapt_recipe_to_staple(extracted_recipe: dict, staple_name: str) -> dict | None:
    """抽出済みレシピを主食指定に合わせて Gemini で再構成する。"""
    if not staple_name.strip():
        return extracted_recipe

    client = genai.Client(api_key=settings.google_api_key)
    prompt = RECIPE_STAPLE_ADAPT_PROMPT_TEMPLATE.format(
        staple_name=staple_name.strip(),
        original_recipe_json=json.dumps(extracted_recipe, ensure_ascii=False),
    )

    wait = GEMINI_RETRY_WAIT
    for attempt in range(MAX_RETRIES_GEMINI + 1):
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(client.models.generate_content, model=VIDEO_MODEL, contents=[prompt]),
                timeout=GEMINI_TIMEOUT,
            )
            data = _parse_gemini_json(response.text)
            if data and _validate_extracted_recipe(data) and _matches_staple(data, staple_name):
                return data

            logger.info(
                "Staple adaptation failed validation (attempt=%d, staple=%s)",
                attempt + 1,
                staple_name,
            )
            if attempt < MAX_RETRIES_GEMINI:
                await asyncio.sleep(wait)
                wait *= 2
        except TimeoutError:
            logger.warning("Gemini staple adaptation timed out (attempt %d)", attempt + 1)
            if attempt < MAX_RETRIES_GEMINI:
                await asyncio.sleep(wait)
                wait *= 2
        except Exception:
            logger.exception("Gemini staple adaptation error (attempt %d)", attempt + 1)
            if attempt < MAX_RETRIES_GEMINI:
                await asyncio.sleep(wait)
                wait *= 2
    return None


async def extract_recipe_from_media(media_path: Path) -> dict | None:
    """Gemini File API でアップロード → マルチモーダル分析。

    Returns: recipe dict or None
    """
    client = genai.Client(api_key=settings.google_api_key)
    uploaded_file = None

    try:
        # 1. ファイルアップロード
        uploaded_file = await asyncio.wait_for(
            asyncio.to_thread(client.files.upload, file=media_path),
            timeout=GEMINI_TIMEOUT,
        )

        # 2. ACTIVE までポーリング（最大 60 秒）
        for _ in range(30):
            if uploaded_file.state.name == "ACTIVE":
                break
            await asyncio.sleep(2)
            uploaded_file = await asyncio.wait_for(
                asyncio.to_thread(client.files.get, name=uploaded_file.name),
                timeout=GEMINI_TIMEOUT,
            )
        else:
            logger.warning("Gemini file upload did not become ACTIVE: %s", media_path.name)
            return None

        # 3. リトライ付き generate_content
        wait = GEMINI_RETRY_WAIT
        for attempt in range(MAX_RETRIES_GEMINI + 1):
            try:
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        client.models.generate_content,
                        model=VIDEO_MODEL,
                        contents=[uploaded_file, RECIPE_EXTRACTION_PROMPT],
                    ),
                    timeout=GEMINI_TIMEOUT,
                )
                data = _parse_gemini_json(response.text)
                if data and _validate_extracted_recipe(data):
                    return data
                if data:
                    logger.info("Gemini extraction failed validation (attempt %d)", attempt + 1)
                else:
                    logger.info("Gemini returned unparseable JSON (attempt %d)", attempt + 1)
                if attempt < MAX_RETRIES_GEMINI:
                    await asyncio.sleep(wait)
                    wait *= 2
            except TimeoutError:
                logger.warning("Gemini extraction timed out (attempt %d)", attempt + 1)
                if attempt < MAX_RETRIES_GEMINI:
                    await asyncio.sleep(wait)
                    wait *= 2
            except Exception:
                logger.exception("Gemini generate_content error (attempt %d)", attempt + 1)
                if attempt < MAX_RETRIES_GEMINI:
                    await asyncio.sleep(wait)
                    wait *= 2

        return None
    finally:
        # 5. アップロード済みファイルを削除
        if uploaded_file:
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(client.files.delete, name=uploaded_file.name),
                    timeout=GEMINI_TIMEOUT,
                )
            except Exception:
                logger.warning("Failed to delete Gemini uploaded file: %s", uploaded_file.name)


def _split_text_for_llm(text: str, max_chars: int = 1600) -> list[str]:
    lines = [line for line in text.splitlines() if line.strip()]
    chunks: list[str] = []
    cur: list[str] = []
    cur_len = 0
    for line in lines:
        line_len = len(line) + 1
        if cur and cur_len + line_len > max_chars:
            chunks.append("\n".join(cur))
            cur = [line]
            cur_len = line_len
        else:
            cur.append(line)
            cur_len += line_len
    if cur:
        chunks.append("\n".join(cur))
    return chunks


async def _naturalize_transcript_for_recipe(transcript_text: str, is_generated: bool) -> str:
    """自動字幕の場合のみ Gemini で自然化。長文は分割実行する。"""
    if not is_generated:
        return transcript_text
    if not settings.google_api_key:
        return transcript_text

    parts = _split_text_for_llm(transcript_text, max_chars=1600)
    out_parts: list[str] = []
    for part in parts:
        try:
            out_parts.append(await naturalize_auto_transcript(part))
        except Exception:
            logger.warning("Transcript naturalization fallback to raw chunk")
            out_parts.append(part)
    return "\n".join(out_parts).strip()


async def extract_recipe_from_transcript_text(
    transcript_text: str,
    video_title: str,
    staple_name: str,
) -> dict | None:
    """文字起こしテキストから Gemini でレシピ JSON を抽出する。"""
    if not settings.google_api_key:
        logger.warning("GOOGLE_API_KEY is not set; cannot extract recipe from transcript")
        return None
    if not transcript_text.strip():
        return None

    client = genai.Client(api_key=settings.google_api_key)
    prompt = RECIPE_FROM_TRANSCRIPT_PROMPT_TEMPLATE.format(
        staple_name=staple_name or "",
        video_title=video_title,
        transcript_text=transcript_text[:20000],
    )

    wait = GEMINI_RETRY_WAIT
    for attempt in range(MAX_RETRIES_GEMINI + 1):
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(client.models.generate_content, model=VIDEO_MODEL, contents=[prompt]),
                timeout=GEMINI_TIMEOUT,
            )
            data = _parse_gemini_json(response.text)
            if data and _validate_extracted_recipe(data):
                if staple_name and not _matches_staple(data, staple_name):
                    logger.info("Transcript extraction succeeded but staple mismatch: %s", staple_name)
                else:
                    return data
            if attempt < MAX_RETRIES_GEMINI:
                await asyncio.sleep(wait)
                wait *= 2
        except TimeoutError:
            logger.warning("Gemini transcript extraction timed out (attempt %d)", attempt + 1)
            if attempt < MAX_RETRIES_GEMINI:
                await asyncio.sleep(wait)
                wait *= 2
        except Exception:
            logger.exception("Gemini transcript extraction error (attempt %d)", attempt + 1)
            if attempt < MAX_RETRIES_GEMINI:
                await asyncio.sleep(wait)
                wait *= 2
    return None
