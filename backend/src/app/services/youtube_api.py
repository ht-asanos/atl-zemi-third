"""YouTube Data API 呼び出し

チャンネル解決・動画一覧取得など YouTube Data API v3 とのやり取りを担う。
"""

import asyncio
import logging
import re

import httpx

logger = logging.getLogger(__name__)

# --- YouTube Data API 定数 ---
MAX_RETRIES_YT_API = 2
YT_API_RETRY_WAIT = 2.0
YT_API_BASE = "https://www.googleapis.com/youtube/v3"

# --- コスト制御 ---
DEFAULT_MAX_RESULTS = 10
MAX_DAILY_VIDEOS = 30
MAX_VIDEO_DURATION_MIN = 30

SHORTS_MARKERS = (
    "#shorts",
    "#ショート",
    "/shorts/",
)


class QuotaExceededError(Exception):
    """YouTube API quota 超過"""


def _is_probable_shorts(item: dict) -> bool:
    """search.list の item が Shorts らしいかを判定する。"""
    snippet = item.get("snippet", {})
    title = str(snippet.get("title", "") or "")
    description = str(snippet.get("description", "") or "")

    title_l = title.lower()
    combined_l = f"{title}\n{description}".lower()

    if any(marker in combined_l for marker in SHORTS_MARKERS):
        return True

    # タイトル先頭に "Shorts" を含むケースを拾う
    if re.match(r"^\s*[【\[\(]?\s*shorts\b", title_l):
        return True

    return False


# ---------------------------------------------------------------------------
# チャンネル解決（フォールバック付き）
# ---------------------------------------------------------------------------


async def resolve_channel_id(
    http_client: httpx.AsyncClient,
    api_key: str,
    handle: str,
) -> str | None:
    """@ハンドル → チャンネル ID 解決。

    1. channels.list(forHandle=handle) を試行
    2. 失敗時: search.list(type=channel, q=handle) でフォールバック
    3. 両方失敗で None 返却
    """
    clean_handle = handle.lstrip("@")

    # 方法1: forHandle
    for attempt in range(MAX_RETRIES_YT_API + 1):
        try:
            resp = await http_client.get(
                f"{YT_API_BASE}/channels",
                params={"part": "id", "forHandle": clean_handle, "key": api_key},
            )
            if resp.status_code == 403:
                logger.warning("YouTube API quota exceeded during channel resolution")
                raise QuotaExceededError()
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("items", [])
                if items:
                    return items[0]["id"]
            break  # 200 だが items 空 → フォールバックへ
        except (httpx.HTTPError, QuotaExceededError):
            if attempt < MAX_RETRIES_YT_API:
                await asyncio.sleep(YT_API_RETRY_WAIT)
            else:
                raise

    # 方法2: search フォールバック
    for attempt in range(MAX_RETRIES_YT_API + 1):
        try:
            resp = await http_client.get(
                f"{YT_API_BASE}/search",
                params={
                    "part": "snippet",
                    "type": "channel",
                    "q": clean_handle,
                    "maxResults": 1,
                    "key": api_key,
                },
            )
            if resp.status_code == 403:
                logger.warning("YouTube API quota exceeded during search fallback")
                raise QuotaExceededError()
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("items", [])
                if items:
                    return items[0]["snippet"]["channelId"]
            break
        except (httpx.HTTPError, QuotaExceededError):
            if attempt < MAX_RETRIES_YT_API:
                await asyncio.sleep(YT_API_RETRY_WAIT)
            else:
                raise

    logger.warning("Could not resolve channel ID for handle: %s", handle)
    return None


# ---------------------------------------------------------------------------
# 動画 ID 一覧取得
# ---------------------------------------------------------------------------


async def fetch_channel_video_ids(
    http_client: httpx.AsyncClient,
    api_key: str,
    channel_id: str,
    max_results: int = 10,
) -> list[dict]:
    """search.list で最新動画 ID リストを取得。

    Returns: [{"video_id": "...", "title": "...", "published_at": "..."}, ...]
    """
    for attempt in range(MAX_RETRIES_YT_API + 1):
        try:
            resp = await http_client.get(
                f"{YT_API_BASE}/search",
                params={
                    "part": "snippet",
                    "channelId": channel_id,
                    "type": "video",
                    "order": "date",
                    "maxResults": max_results,
                    "key": api_key,
                },
            )
            if resp.status_code == 403:
                logger.warning("YouTube API quota exceeded during video list fetch")
                raise QuotaExceededError()
            resp.raise_for_status()
            data = resp.json()
            results = []
            for item in data.get("items", []):
                vid = item.get("id", {}).get("videoId")
                snippet = item.get("snippet", {})
                if vid and not _is_probable_shorts(item):
                    results.append(
                        {
                            "video_id": vid,
                            "title": snippet.get("title", ""),
                            "published_at": snippet.get("publishedAt", ""),
                        }
                    )
            return results
        except QuotaExceededError:
            raise
        except httpx.HTTPError:
            if attempt < MAX_RETRIES_YT_API:
                await asyncio.sleep(YT_API_RETRY_WAIT)
            else:
                logger.exception("Failed to fetch video list for channel %s", channel_id)
                return []
    return []


async def fetch_channel_videos_by_query(
    http_client: httpx.AsyncClient,
    api_key: str,
    channel_id: str,
    query: str,
    max_results: int = 25,
) -> list[dict]:
    """search.list(channelId + q) で動画候補を取得する。"""
    for attempt in range(MAX_RETRIES_YT_API + 1):
        try:
            resp = await http_client.get(
                f"{YT_API_BASE}/search",
                params={
                    "part": "snippet",
                    "channelId": channel_id,
                    "type": "video",
                    "order": "date",
                    "q": query,
                    "maxResults": max_results,
                    "key": api_key,
                },
            )
            if resp.status_code == 403:
                logger.warning("YouTube API quota exceeded during query video fetch")
                raise QuotaExceededError()
            resp.raise_for_status()
            data = resp.json()
            out: list[dict] = []
            for item in data.get("items", []):
                vid = item.get("id", {}).get("videoId")
                snippet = item.get("snippet", {})
                if vid and not _is_probable_shorts(item):
                    out.append(
                        {
                            "video_id": vid,
                            "title": snippet.get("title", ""),
                            "published_at": snippet.get("publishedAt", ""),
                        }
                    )
            return out
        except QuotaExceededError:
            raise
        except httpx.HTTPError:
            if attempt < MAX_RETRIES_YT_API:
                await asyncio.sleep(YT_API_RETRY_WAIT)
            else:
                logger.exception("Failed to fetch queried videos for channel %s", channel_id)
                return []
    return []
