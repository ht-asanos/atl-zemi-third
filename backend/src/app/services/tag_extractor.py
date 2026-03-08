import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Literal

from app.config import settings
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

VALID_TAGS = frozenset(
    {
        "too_hard",
        "cannot_complete_reps",
        "forearm_sore",
        "bored_staple",
        "too_much_food",
    }
)

SYSTEM_PROMPT = """あなたはフィットネス・食事管理アプリのフィードバック解析AIです。
ユーザーの日本語フリーテキストから、以下の5つのタグのうち該当するものをJSON配列で返してください。
該当しないタグは含めないでください。

タグ一覧:
- "too_hard": トレーニングがきつすぎる
- "cannot_complete_reps": レップ数をこなせない
- "forearm_sore": 前腕が痛い・疲れている
- "bored_staple": 主食に飽きた
- "too_much_food": 食事量が多すぎる

JSON配列のみを返してください。例: ["too_hard", "bored_staple"]
該当なしの場合: []"""

MAX_RETRIES = 3
BACKOFF_SECONDS = [1, 2, 4]


@dataclass
class ExtractionResult:
    tags: list[str] = field(default_factory=list)
    status: Literal["success", "partial", "failed"] = "success"


async def extract_tags(text: str) -> ExtractionResult:
    if not settings.openai_api_key:
        logger.error("OpenAI API key is not configured")
        return ExtractionResult(tags=[], status="failed")

    client = AsyncOpenAI(api_key=settings.openai_api_key)

    for attempt in range(MAX_RETRIES):
        try:
            response = await client.chat.completions.create(
                model=settings.openai_model,
                temperature=0,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
            )
            content = response.choices[0].message.content or "[]"
            raw_tags = json.loads(content)

            if not isinstance(raw_tags, list):
                return ExtractionResult(tags=[], status="success")

            valid = [t for t in raw_tags if isinstance(t, str) and t in VALID_TAGS]
            return ExtractionResult(tags=valid, status="success")

        except (json.JSONDecodeError, IndexError, KeyError) as e:
            logger.warning("Tag extraction parse error (attempt %d): %s", attempt + 1, e)
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(BACKOFF_SECONDS[attempt])
                continue
            return ExtractionResult(tags=[], status="failed")

        except Exception:
            logger.error("Tag extraction API error (attempt %d)", attempt + 1, exc_info=True)
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(BACKOFF_SECONDS[attempt])
                continue
            return ExtractionResult(tags=[], status="failed")

    return ExtractionResult(tags=[], status="failed")
