"""MEXT 食品成分データベースのスクレイパー

CLI (data_loader.py) および backfill API から利用する。
"""

import asyncio
import logging
import re

import httpx
from app.models.food import MextFood
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://fooddb.mext.go.jp"
SEMAPHORE = asyncio.Semaphore(3)
REQUEST_INTERVAL = 0.5
FREEWORD_SELECT_PATH = "/freeword/fword_select.pl"

# fooddb のカテゴリ一覧検索 URL(result_top.pl) は ERR_15 を返すことがあるため、
# 安定して取得できるフリーワード検索のカテゴリ代表語へフォールバックする。
CATEGORY_SEARCH_KEYWORDS: dict[str, str] = {
    "01": "米",
    "02": "じゃがいも",
    "03": "砂糖",
    "04": "大豆",
    "05": "ごま",
    "06": "野菜",
    "07": "果実",
    "08": "きのこ",
    "09": "海藻",
    "10": "魚",
    "11": "肉",
    "12": "卵",
    "13": "牛乳",
    "14": "油",
    "15": "菓子",
    "16": "コーヒー",
    "17": "しょうゆ",
    "18": "加工食品",
}


def _parse_float(text: str) -> float:
    """栄養素値をパースする。"Tr", "-", "(0)" 等を 0 として扱う。"""
    if not text:
        return 0.0
    cleaned = re.sub(r"[()（）]", "", text.strip()).replace(",", "")
    cleaned = cleaned.replace("＜", "").replace("<", "")
    cleaned = cleaned.replace("Tr", "0").replace("tr", "0").replace("-", "0").replace("—", "0")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _extract_row_value_text(row: BeautifulSoup, unit: str) -> str:
    """栄養素行から「値」を優先的に抽出する。"""
    num_cell = row.select_one("td.num")
    if num_cell:
        v = num_cell.get_text(strip=True)
        if v:
            return v

    marker_cell = row.select_one("td.marker")
    if marker_cell:
        v = marker_cell.get_text(strip=True)
        if v and v != unit:
            return v

    # クラス構造が変わった場合のフォールバック:
    # 行内セルから数値らしいトークンを選ぶ（単位文字列は除外）
    tokens = [td.get_text(strip=True) for td in row.select("td")]
    for token in tokens:
        if not token or token == unit:
            continue
        if re.search(r"\d", token) or token in {"Tr", "tr", "-", "—"}:
            return token

    return ""


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
    parts = item_no.split("_")
    if len(parts) >= 2 and len(parts[1]) == 2 and parts[1].isdigit():
        # 新形式: 7_11_11214 -> 11 をカテゴリコードとして扱う
        category_code = parts[1]
    else:
        # 旧形式: 11_01088_7 -> 11
        category_code = parts[0] if parts else "00"
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
    kcal = protein = fat = carbs = 0.0
    fiber = sodium = calcium = iron = None
    parsed_any = False

    # 現行 fooddb レイアウト: td.pr_name と td.num / td.marker の組
    for row in soup.select("table tr"):
        name_cell = row.select_one("td.pr_name")
        if not name_cell:
            continue

        label = name_cell.get_text(strip=True)
        unit_cell = row.select_one("td.pr_unit")
        unit = unit_cell.get_text(strip=True) if unit_cell else ""
        value_text = _extract_row_value_text(row, unit)
        raw_data[label] = value_text
        parsed_any = True

        if label == "エネルギー" and unit == "kcal":
            kcal = _parse_float(value_text)
        elif label == "たんぱく質":
            protein = _parse_float(value_text)
        elif label == "脂質":
            fat = _parse_float(value_text)
        elif label == "炭水化物":
            carbs = _parse_float(value_text)
        elif label == "食物繊維総量":
            fiber = _parse_float(value_text)
        elif label == "ナトリウム":
            sodium = _parse_float(value_text)
        elif label == "カルシウム":
            calcium = _parse_float(value_text)
        elif label == "鉄":
            iron = _parse_float(value_text)

    # 旧HTML向けフォールバック
    if not parsed_any:
        for row in soup.select("table tr"):
            cells = row.select("td, th")
            if len(cells) < 2:
                continue
            label = cells[0].get_text(strip=True)
            value_text = cells[-1].get_text(strip=True)
            raw_data[label] = value_text

            if "エネルギー" in label and "kJ" not in label:
                kcal = _parse_float(value_text)
            elif label == "たんぱく質" or ("たんぱく質" in label and "アミノ酸" not in label):
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
        raw_data={"source": "scrape", **raw_data},
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
    """HTML から ITEM_NO のリストを抽出する（共通ヘルパー）。

    fooddb では結果画面に ITEM_NO がリンク形式または checkbox value で存在する。
    """
    soup = BeautifulSoup(html, "html.parser")
    item_nos: list[str] = []
    seen: set[str] = set()

    for link in soup.select("a[href*='ITEM_NO=']"):
        href = link.get("href", "")
        match = re.search(r"ITEM_NO=([^&]+)", href)
        if match:
            item_no = match.group(1)
            if item_no not in seen:
                seen.add(item_no)
                item_nos.append(item_no)

    for checkbox in soup.select("input[name='ITEM_NO'][value]"):
        item_no = checkbox.get("value", "").strip()
        if item_no and item_no not in seen:
            seen.add(item_no)
            item_nos.append(item_no)

    return item_nos


async def scrape_category_list(client: httpx.AsyncClient, category_code: str) -> list[str]:
    """カテゴリページから ITEM_NO のリストを取得する。"""
    # 旧導線: result_top.pl（現在は ERR_15 を返す場合がある）
    async with SEMAPHORE:
        url = f"{BASE_URL}/result/result_top.pl?USER_ID=&MODE=2&CATEGORY_CODE={category_code}"
        resp = await client.get(url, follow_redirects=True)
        await asyncio.sleep(REQUEST_INTERVAL)

    if resp.status_code != 200:
        legacy_items: list[str] = []
    else:
        legacy_items = _extract_item_nos(resp.text)
        if legacy_items:
            return legacy_items

    keyword = CATEGORY_SEARCH_KEYWORDS.get(category_code)
    if not keyword:
        return []
    logger.info("MEXT category fallback to freeword search: code=%s keyword=%s", category_code, keyword)
    return await _search_item_nos_by_freeword(client, keyword)


async def _search_item_nos_by_freeword(client: httpx.AsyncClient, keyword: str) -> list[str]:
    async with SEMAPHORE:
        resp = await client.post(
            f"{BASE_URL}{FREEWORD_SELECT_PATH}",
            data={"SEARCH_WORD": keyword, "USER_ID": "", "function1": "検索"},
            follow_redirects=True,
        )
        await asyncio.sleep(REQUEST_INTERVAL)

    if resp.status_code != 200:
        logger.warning("MEXT freeword search HTTP %d for '%s'", resp.status_code, keyword)
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
    url = f"{BASE_URL}{FREEWORD_SELECT_PATH}"
    retries = 2

    for attempt in range(retries):
        try:
            async with SEMAPHORE:
                resp = await client.post(
                    url,
                    data={"SEARCH_WORD": name, "USER_ID": "", "function1": "検索"},
                    follow_redirects=True,
                )
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
