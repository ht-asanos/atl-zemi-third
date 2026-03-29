"""YouTube 字幕取得 + 品質評価 + 自動字幕の自然化。"""

from __future__ import annotations

import asyncio
import logging
import re
from collections import Counter
from typing import Any

import requests
from app.config import settings
from google import genai

logger = logging.getLogger(__name__)

TRANSCRIPT_MODEL = "gemini-2.5-flash"
TRANSCRIPT_TIMEOUT = 45
LOW_QUALITY_TRANSCRIPT_SCORE = 70.0

PUNCTUATIONS = "。、，．,.!?！？"

NATURALIZE_PROMPT = """\
あなたはトレーニング動画字幕の校正者です。以下の字幕テキストを、意味を変えずに自然な日本語へ整えてください。

制約:
- 意味を変えない
- 事実を追加しない
- トレーニング名・種目名・姿勢名・部位名は勝手に一般語へ言い換えない
- 回数・左右・秒数・重量・順序は絶対に変えない
- 「できるなら」「次は」「挑戦できます」「左右3回」など進度関係の表現を保持する
- 口語は維持してよい
- 句読点と改行を適切に補う
- 明らかな誤字のみ最小限修正
- 不明な語は無理に補完せず、そのまま残す
- 出力は整形後テキストのみ（説明不要）

字幕:
{text}
"""


def extract_video_id(video_ref: str) -> str | None:
    """URL or video id から YouTube の video id を抽出する。"""
    src = video_ref.strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", src):
        return src

    patterns = [
        r"(?:v=)([A-Za-z0-9_-]{11})",
        r"(?:youtu\.be/)([A-Za-z0-9_-]{11})",
        r"(?:youtube\.com/shorts/)([A-Za-z0-9_-]{11})",
        r"(?:embed/)([A-Za-z0-9_-]{11})",
    ]
    for p in patterns:
        m = re.search(p, src)
        if m:
            return m.group(1)
    return None


def assess_transcript_quality(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """字幕の粗い品質指標を返す。"""
    texts = [str(x.get("text", "")).strip() for x in entries if str(x.get("text", "")).strip()]
    merged = " ".join(texts)
    total_chars = len(merged)
    punct_count = sum(1 for c in merged if c in PUNCTUATIONS)
    punctuation_density = (punct_count / total_chars) if total_chars else 0.0
    avg_segment_len = (sum(len(t) for t in texts) / len(texts)) if texts else 0.0

    normalized = [re.sub(r"\s+", "", t) for t in texts]
    dup_counter = Counter(normalized)
    duplicate_segments = sum(1 for _, cnt in dup_counter.items() if cnt > 1)
    duplicate_ratio = (duplicate_segments / len(texts)) if texts else 0.0

    score = 100.0
    if punctuation_density < 0.01:
        score -= 30
    elif punctuation_density < 0.03:
        score -= 15
    if avg_segment_len < 6:
        score -= 20
    if duplicate_ratio > 0.08:
        score -= 15
    score = max(0.0, min(100.0, score))

    notes: list[str] = []
    if punctuation_density < 0.02:
        notes.append("句読点が少ない")
    if avg_segment_len < 6:
        notes.append("セグメントが短く断片的")
    if duplicate_ratio > 0.08:
        notes.append("重複セグメントが多い")

    return {
        "segment_count": len(texts),
        "total_chars": total_chars,
        "punctuation_density": round(punctuation_density, 4),
        "avg_segment_len": round(avg_segment_len, 2),
        "duplicate_ratio": round(duplicate_ratio, 4),
        "quality_score": round(score, 1),
        "notes": notes,
    }


def get_transcript_naturalization_reason(
    transcript: dict[str, Any],
    *,
    quality_threshold: float = LOW_QUALITY_TRANSCRIPT_SCORE,
) -> str | None:
    """自然化を適用すべき理由を返す。不要なら None。"""
    text = str(transcript.get("text", "") or "").strip()
    if not text:
        return None
    if bool(transcript.get("is_generated")):
        return "auto_generated"

    quality = transcript.get("quality") or {}
    try:
        quality_score = float(quality.get("quality_score"))
    except (TypeError, ValueError):
        quality_score = None
    if quality_score is not None and quality_score < quality_threshold:
        return "low_quality"
    return None


def _normalize_transcript_entries(fetched: Any) -> list[dict[str, Any]]:
    """youtube-transcript-api のバージョン差分を吸収して dict 配列へ変換。"""
    if hasattr(fetched, "to_raw_data"):
        raw = fetched.to_raw_data()
        if isinstance(raw, list):
            return [dict(x) for x in raw]

    entries: list[dict[str, Any]] = []
    for item in fetched:
        if isinstance(item, dict):
            entries.append(dict(item))
            continue
        text = getattr(item, "text", None)
        start = getattr(item, "start", None)
        duration = getattr(item, "duration", None)
        entries.append({"text": text, "start": start, "duration": duration})
    return entries


async def fetch_transcript(video_ref: str, languages: list[str] | None = None) -> dict[str, Any]:
    """youtube-transcript-api で字幕取得。"""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError as e:
        raise RuntimeError("youtube-transcript-api が未インストールです。`uv sync` を実行してください。") from e

    langs = languages or ["ja", "ja-JP", "en"]
    video_id = extract_video_id(video_ref)
    if not video_id:
        raise ValueError(f"video id を抽出できません: {video_ref}")

    http_client = requests.Session()
    http_client.verify = settings.youtube_transcript_verify_ssl
    try:
        api = YouTubeTranscriptApi(http_client=http_client)
        transcript_list = await asyncio.to_thread(api.list, video_id)

        chosen = None
        for lang in langs:
            try:
                chosen = await asyncio.to_thread(transcript_list.find_transcript, [lang])
                break
            except Exception:
                continue
        if chosen is None:
            chosen = await asyncio.to_thread(transcript_list.find_generated_transcript, langs)

        fetched = await asyncio.to_thread(chosen.fetch)
        entries = _normalize_transcript_entries(fetched)
        quality = assess_transcript_quality(entries)
        return {
            "video_id": video_id,
            "language_code": getattr(chosen, "language_code", None),
            "language": getattr(chosen, "language", None),
            "is_generated": bool(getattr(chosen, "is_generated", False)),
            "is_translatable": bool(getattr(chosen, "is_translatable", False)),
            "entries": entries,
            "text": "\n".join(str(x.get("text", "")).strip() for x in entries if str(x.get("text", "")).strip()),
            "quality": quality,
        }
    finally:
        http_client.close()


async def naturalize_auto_transcript(text: str) -> str:
    """自動字幕を Gemini で自然な日本語へ整形する。"""
    if not settings.google_api_key:
        raise RuntimeError("GOOGLE_API_KEY が未設定です。")

    src = text.strip()
    if not src:
        return src

    client = genai.Client(api_key=settings.google_api_key)
    prompt = NATURALIZE_PROMPT.format(text=src)
    response = await asyncio.wait_for(
        asyncio.to_thread(client.models.generate_content, model=TRANSCRIPT_MODEL, contents=[prompt]),
        timeout=TRANSCRIPT_TIMEOUT,
    )
    out = (response.text or "").strip()
    if not out:
        logger.warning("Gemini naturalize returned empty text")
        return src
    return out
