"""楽天レシピ API クライアント（バックグラウンドジョブ専用）

API リクエスト中には呼ばない。data_loader 経由のみ。
レシピ本文・手順は保存せず、recipe_url（リンク）のみ保持（利用規約対策）。
"""

import asyncio

import httpx

RAKUTEN_API_BASE = "https://openapi.rakuten.co.jp/recipems/api/Recipe"
REQUEST_INTERVAL = 1.0


async def fetch_category_list(client: httpx.AsyncClient, app_id: str, access_key: str) -> list[dict]:
    """楽天レシピのカテゴリ一覧を取得する。"""
    url = f"{RAKUTEN_API_BASE}/CategoryList/20170426"
    params = {"applicationId": app_id, "format": "json"}
    headers = {"Authorization": f"Bearer {access_key}"}
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
    params = {"applicationId": app_id, "categoryId": category_id, "format": "json"}
    headers = {"Authorization": f"Bearer {access_key}"}
    resp = await client.get(url, params=params, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    return data.get("result", [])


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
        raw = await fetch_category_ranking(client, app_id, access_key, cat_id)
        all_recipes.extend(parse_ranking_recipes(raw))
        await asyncio.sleep(REQUEST_INTERVAL)
    return all_recipes
