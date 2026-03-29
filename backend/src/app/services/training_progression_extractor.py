from __future__ import annotations

import asyncio
import json
import logging
import re

from app.config import settings
from app.schemas.training_progression import TrainingProgressionExtractedEdge
from google import genai

logger = logging.getLogger(__name__)

PROGRESSION_MODEL = "gemini-2.5-flash"
PROGRESSION_TIMEOUT = 45

PROGRESSION_EXTRACTION_PROMPT = """\
あなたはトレーニング進度の関係抽出アシスタントです。
以下の字幕テキストから、ある種目ができることを条件に次の種目へ進める
段階的な関係だけを抽出してください。

出力は JSON 配列のみ:
[
  {{
    "from_label": "懸垂",
    "from_reps": 10,
    "to_label": "マッスルアップ",
    "to_reps": 1,
    "evidence_text": "懸垂が10回できるならマッスルアップ1回できます",
    "confidence": 0.92
  }}
]

ルール:
- 「AがX回できるならBがY回できる」だけでなく、以下も抽出対象:
  - 「AがX回できるならBに挑戦できる」
  - 「Aができるなら次はB」
  - 「Aが左右3回できるならBが1回できる」
  - 「A 10回 → B 5回」のような省略表現
- from_reps / to_reps は整数のみ
- 「左右3回」は 3 として抽出する
- from_reps か to_reps のどちらかを字幕から特定できない曖昧な関係は除外
- 秒数、重量、距離ベースの関係は除外
- ストレッチや一般論ではなく、進度関係として明示されているものだけを抽出
- confidence は 0 から 1
- 1件もなければ [] を返す
- JSON 以外の説明を書かない

抽出例:
- 「懸垂が10回できるならマッスルアップ1回できます」
  -> from_label=懸垂, from_reps=10, to_label=マッスルアップ, to_reps=1
- 「ディップスバーの上で5回スイングできるなら次はタックプラン」
  -> from_label=ディップスバーの上でスイング, from_reps=5, to_label=タックプラン, to_reps=1
- 「この動きが左右3回できたら次はブリッジです」
  -> from_reps=3
- 「30秒キープできたら次へ」
  -> 除外
- 「重り10kgで5回できるなら」
  -> 除外
- 「そのうちできるようになります」
  -> 除外

動画タイトル:
{video_title}

字幕:
{transcript_text}
"""


def _parse_json_array(text: str) -> list[dict]:
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        text = match.group(1)
    payload = text.strip()
    if not payload:
        return []
    data = json.loads(payload)
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


async def extract_progression_edges_from_transcript(
    *,
    video_title: str,
    transcript_text: str,
) -> list[TrainingProgressionExtractedEdge]:
    if not settings.google_api_key:
        raise RuntimeError("GOOGLE_API_KEY が未設定です。")

    client = genai.Client(api_key=settings.google_api_key)
    prompt = PROGRESSION_EXTRACTION_PROMPT.format(
        video_title=video_title.strip(),
        transcript_text=transcript_text.strip(),
    )
    response = await asyncio.wait_for(
        asyncio.to_thread(client.models.generate_content, model=PROGRESSION_MODEL, contents=[prompt]),
        timeout=PROGRESSION_TIMEOUT,
    )
    raw_items = _parse_json_array(response.text or "[]")
    edges: list[TrainingProgressionExtractedEdge] = []
    for item in raw_items:
        try:
            edge = TrainingProgressionExtractedEdge(**item)
        except Exception:
            logger.warning("Invalid progression edge payload: %s", item)
            continue
        edges.append(edge)
    return edges
