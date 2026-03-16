"""楽天レシピ API クライアント（バックグラウンドジョブ専用）

API リクエスト中には呼ばない。data_loader 経由のみ。
レシピ本文・手順は保存せず、recipe_url（リンク）のみ保持（利用規約対策）。
"""

import asyncio
import logging
from collections.abc import Iterable

import httpx

RAKUTEN_API_BASE = "https://openapi.rakuten.co.jp/recipems/api/Recipe"
REQUEST_INTERVAL = 2.0
MAX_RETRIES_ON_429 = 3
RETRY_BASE_SECONDS = 2.0

logger = logging.getLogger(__name__)


def _auth_params_and_headers(app_id: str, access_key: str) -> tuple[dict[str, str], dict[str, str]]:
    """楽天API共通の認証パラメータ/ヘッダーを返す。"""
    params = {
        "applicationId": app_id,
        "accessKey": access_key,
        "format": "json",
    }
    headers = {"Authorization": f"Bearer {access_key}"}
    return params, headers


async def fetch_category_list(client: httpx.AsyncClient, app_id: str, access_key: str) -> list[dict]:
    """楽天レシピのカテゴリ一覧を取得する。"""
    url = f"{RAKUTEN_API_BASE}/CategoryList/20170426"
    params, headers = _auth_params_and_headers(app_id, access_key)
    resp = await client.get(url, params=params, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    result = data.get("result", {})
    categories: list[dict] = []
    for key in ("large", "medium", "small"):
        categories.extend(result.get(key, []))
    return categories


async def fetch_category_ranking(
    client: httpx.AsyncClient, app_id: str, access_key: str, category_id: str
) -> list[dict]:
    """カテゴリ別ランキングレシピを取得する。"""
    url = f"{RAKUTEN_API_BASE}/CategoryRanking/20170426"
    params, headers = _auth_params_and_headers(app_id, access_key)
    params["categoryId"] = category_id
    resp: httpx.Response | None = None
    for attempt in range(MAX_RETRIES_ON_429 + 1):
        resp = await client.get(url, params=params, headers=headers)
        if resp.status_code != 429:
            break

        if attempt >= MAX_RETRIES_ON_429:
            break

        retry_after = resp.headers.get("Retry-After")
        try:
            wait_s = float(retry_after) if retry_after else RETRY_BASE_SECONDS * (attempt + 1)
        except ValueError:
            wait_s = RETRY_BASE_SECONDS * (attempt + 1)
        logger.warning("Rakuten API rate-limited for category=%s, retry in %.1fs", category_id, wait_s)
        await asyncio.sleep(wait_s)

    assert resp is not None
    resp.raise_for_status()
    data = resp.json()
    return data.get("result", [])


def build_category_index(categories: list[dict]) -> list[dict]:
    """カテゴリ一覧（large/medium/small混在）から検索用インデックスを作る。"""
    # 仕様: large は parent なし、medium は parent=large_id、small は parent=medium_id
    large_ids: set[str] = set()
    medium_parent: dict[str, str] = {}  # medium_id -> large_id
    indexed: list[dict] = []

    normalized: list[tuple[str, str, str]] = []  # (cid, cname, parent)
    for c in categories:
        cid = str(c.get("categoryId", "")).strip()
        cname = str(c.get("categoryName", "")).strip()
        parent = str(c.get("parentCategoryId", "")).strip()
        if not cid or not cname:
            continue
        normalized.append((cid, cname, parent))

    for cid, _, parent in normalized:
        if not parent:
            large_ids.add(cid)

    for cid, cname, parent in normalized:
        if not parent:
            indexed.append({"category_id": cid, "category_name": cname, "level": "large"})
        elif parent in large_ids:
            medium_parent[cid] = parent
            indexed.append({"category_id": f"{parent}-{cid}", "category_name": cname, "level": "medium"})

    for cid, cname, parent in normalized:
        if parent in medium_parent:
            large_id = medium_parent[parent]
            indexed.append({"category_id": f"{large_id}-{parent}-{cid}", "category_name": cname, "level": "small"})

    return indexed


def find_category_ids_by_keywords(
    category_index: Iterable[dict],
    keywords: list[str],
    max_categories: int = 30,
) -> list[str]:
    """カテゴリ名にキーワードを含む category_id を抽出する。"""
    keys = [k.strip() for k in keywords if k and k.strip()]
    if not keys:
        return []

    level_rank = {"small": 0, "medium": 1, "large": 2, "unknown": 3}
    matches: list[tuple[int, str]] = []

    for c in category_index:
        name = str(c.get("category_name", ""))
        cid = str(c.get("category_id", ""))
        level = str(c.get("level", "unknown"))
        if not cid or not name:
            continue
        if any(k in name for k in keys):
            matches.append((level_rank.get(level, 99), cid))

    matches.sort(key=lambda x: (x[0], x[1]))
    out: list[str] = []
    seen: set[str] = set()
    for _, cid in matches:
        if cid in seen:
            continue
        seen.add(cid)
        out.append(cid)
        if len(out) >= max_categories:
            break
    return out


def parse_ranking_recipes(raw_recipes: list[dict]) -> list[dict]:
    """楽天 API レスポンスをアプリ内部形式にパースする。"""
    parsed: list[dict] = []
    for r in raw_recipes:
        ingredients = []
        for mat in r.get("recipeMaterial", []):
            if isinstance(mat, str):
                ingredients.append({"ingredient_name": mat, "amount_text": None})
            elif isinstance(mat, dict):
                ingredients.append(
                    {
                        "ingredient_name": mat.get("name", mat.get("item", str(mat))),
                        "amount_text": mat.get("amount"),
                    }
                )

        parsed.append(
            {
                "rakuten_recipe_id": r.get("recipeId"),
                "title": r.get("recipeTitle", ""),
                "description": r.get("recipeDescription", ""),
                "image_url": r.get("foodImageUrl", r.get("mediumImageUrl")),
                "recipe_url": r.get("recipeUrl", ""),
                "rakuten_category_id": r.get("recipeCategoryId"),
                "servings": r.get("recipeYield", 1) or 1,
                "cost_estimate": r.get("recipeCost"),
                "cooking_minutes": _parse_minutes(r.get("recipeIndication")),
                "tags": _extract_tags(r),
                "ingredients": ingredients,
            }
        )
    return parsed


def _parse_minutes(indication: str | None) -> int | None:
    """ "約30分" → 30 のように分数を抽出する。"""
    if not indication:
        return None
    import re

    m = re.search(r"(\d+)", indication)
    return int(m.group(1)) if m else None


def _extract_tags(recipe: dict) -> list[str]:
    """レシピからタグを生成する。"""
    tags: list[str] = []
    if recipe.get("recipeCategoryName"):
        tags.append(recipe["recipeCategoryName"])
    return tags


async def fetch_multiple_categories(
    client: httpx.AsyncClient,
    app_id: str,
    access_key: str,
    category_ids: list[str],
) -> list[dict]:
    """複数カテゴリのランキングレシピを順番に取得する。"""
    all_recipes: list[dict] = []
    for cat_id in category_ids:
        try:
            raw = await fetch_category_ranking(client, app_id, access_key, cat_id)
            all_recipes.extend(parse_ranking_recipes(raw))
        except Exception as e:
            logger.warning("skip category %s due to error: %s", cat_id, e)
        await asyncio.sleep(REQUEST_INTERVAL)
    return all_recipes
