"""MEXT 食品成分データベースのスクレイパー

CLI (data_loader.py) および backfill API から利用する。
"""

import asyncio
import logging
import re
from urllib.parse import quote

import httpx
from app.models.food import MextFood
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://fooddb.mext.go.jp"
SEMAPHORE = asyncio.Semaphore(3)
REQUEST_INTERVAL = 0.5


def _parse_float(text: str) -> float:
    """栄養素値をパースする。"Tr", "-", "(0)" 等を 0 として扱う。"""
    if not text:
        return 0.0
    cleaned = re.sub(r"[()（）]", "", text.strip())
    cleaned = cleaned.replace("Tr", "0").replace("tr", "0").replace("-", "0").replace("—", "0")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def parse_food_detail(html: str, item_no: str) -> MextFood | None:
    """MEXT 食品詳細ページの HTML をパースして MextFood を返す。"""
    soup = BeautifulSoup(html, "html.parser")

    name_tag = soup.select_one("h2.food-name, .food-detail-name, title")
    if not name_tag:
        return None
    name = name_tag.get_text(strip=True)
    # title タグの場合 "食品成分データベース - " を除去
    name = re.sub(r"^食品成分データベース\s*[-–]\s*", "", name)

    # カテゴリ情報
    category_code = item_no.split("_")[0] if "_" in item_no else "00"
    category_map = {
        "01": "穀類",
        "02": "いも及びでん粉類",
        "03": "砂糖及び甘味類",
        "04": "豆類",
        "05": "種実類",
        "06": "野菜類",
        "07": "果実類",
        "08": "きのこ類",
        "09": "藻類",
        "10": "魚介類",
        "11": "肉類",
        "12": "卵類",
        "13": "乳類",
        "14": "油脂類",
        "15": "菓子類",
        "16": "し好飲料類",
        "17": "調味料及び香辛料類",
        "18": "調理加工食品類",
    }
    category_name = category_map.get(category_code, "その他")

    # 栄養素テーブルからデータ取得
    raw_data: dict = {}
    rows = soup.select("table tr")
    kcal = protein = fat = carbs = 0.0
    fiber = sodium = calcium = iron = None

    for row in rows:
        cells = row.select("td, th")
        if len(cells) < 2:
            continue
        label = cells[0].get_text(strip=True)
        value_text = cells[-1].get_text(strip=True)
        raw_data[label] = value_text

        if "エネルギー" in label and "kJ" not in label:
            kcal = _parse_float(value_text)
        elif label == "たんぱく質" or "たんぱく質" in label and "アミノ酸" not in label:
            protein = _parse_float(value_text)
        elif label == "脂質" or (label.startswith("脂質") and "脂肪酸" not in label):
            fat = _parse_float(value_text)
        elif "炭水化物" in label and "利用可能" not in label:
            carbs = _parse_float(value_text)
        elif "食物繊維総量" in label:
            fiber = _parse_float(value_text)
        elif "ナトリウム" in label:
            sodium = _parse_float(value_text)
        elif "カルシウム" in label:
            calcium = _parse_float(value_text)
        elif label == "鉄" or label.startswith("鉄"):
            iron = _parse_float(value_text)

    return MextFood(
        mext_food_id=item_no,
        name=name,
        category_code=category_code,
        category_name=category_name,
        kcal_per_100g=kcal,
        protein_g_per_100g=protein,
        fat_g_per_100g=fat,
        carbs_g_per_100g=carbs,
        fiber_g_per_100g=fiber,
        sodium_mg_per_100g=sodium,
        calcium_mg_per_100g=calcium,
        iron_mg_per_100g=iron,
        raw_data=raw_data,
    )


async def scrape_food_detail(client: httpx.AsyncClient, item_no: str) -> MextFood | None:
    """MEXT 食品詳細ページをスクレイピングして MextFood を返す。"""
    async with SEMAPHORE:
        url = f"{BASE_URL}/details/details.pl?ITEM_NO={item_no}"
        resp = await client.get(url, follow_redirects=True)
        if resp.status_code != 200:
            return None
        await asyncio.sleep(REQUEST_INTERVAL)
        return parse_food_detail(resp.text, item_no)


def _extract_item_nos(html: str) -> list[str]:
    """HTML から ITEM_NO のリストを抽出する（共通ヘルパー）。"""
    soup = BeautifulSoup(html, "html.parser")
    item_nos: list[str] = []
    for link in soup.select("a[href*='ITEM_NO=']"):
        href = link.get("href", "")
        match = re.search(r"ITEM_NO=([^&]+)", href)
        if match:
            item_nos.append(match.group(1))
    return item_nos


async def scrape_category_list(client: httpx.AsyncClient, category_code: str) -> list[str]:
    """カテゴリページから ITEM_NO のリストを取得する。"""
    async with SEMAPHORE:
        url = f"{BASE_URL}/result/result_top.pl?USER_ID=&MODE=2&CATEGORY_CODE={category_code}"
        resp = await client.get(url, follow_redirects=True)
        await asyncio.sleep(REQUEST_INTERVAL)

    if resp.status_code != 200:
        return []

    return _extract_item_nos(resp.text)


async def bulk_scrape_category(client: httpx.AsyncClient, category_code: str) -> list[MextFood]:
    """カテゴリ全体をスクレイピングする。"""
    item_nos = await scrape_category_list(client, category_code)
    results: list[MextFood] = []
    for item_no in item_nos:
        food = await scrape_food_detail(client, item_no)
        if food:
            results.append(food)
    return results


async def search_foods_by_name(
    client: httpx.AsyncClient,
    name: str,
    max_results: int = 5,
) -> list[MextFood]:
    """MEXT 食品 DB をキーワード検索する。

    失敗時は空リストを返す（ログ出力のみ、例外は伝播しない）。
    タイムアウト時は 1 回だけリトライする。
    """
    url = f"{BASE_URL}/result/result_top.pl?MODE=1&SEARCH_WORD={quote(name)}"
    retries = 2

    for attempt in range(retries):
        try:
            async with SEMAPHORE:
                resp = await client.get(url, follow_redirects=True)
                await asyncio.sleep(REQUEST_INTERVAL)

            if resp.status_code != 200:
                logger.warning("MEXT search HTTP %d for '%s'", resp.status_code, name)
                return []

            item_nos = _extract_item_nos(resp.text)
            if not item_nos:
                return []

            # 詳細ページから食品情報を取得
            results: list[MextFood] = []
            for item_no in item_nos[:max_results]:
                food = await scrape_food_detail(client, item_no)
                if food:
                    results.append(food)
            return results

        except httpx.TimeoutException:
            if attempt < retries - 1:
                logger.warning("MEXT search timeout for '%s', retrying...", name)
                continue
            logger.warning("MEXT search timeout for '%s' after retry", name)
            return []
        except Exception:
            logger.warning("MEXT search failed for '%s'", name, exc_info=True)
            return []
