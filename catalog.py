import json
from typing import Dict, Any
import httpx

from app.config import DEFAULT_CATALOG_URL
from app.db import db_get_setting

CATALOG: Dict[str, Any] = {}
SKU_INDEX: Dict[str, Dict[str, Any]] = {}

async def load_catalog() -> bool:
    """
    Загружает каталог из URL (если указан в settings или .env),
    иначе — из локального файла catalog.json.
    """
    global CATALOG, SKU_INDEX
    url = await db_get_setting("catalog_url", DEFAULT_CATALOG_URL)
    data = None
    try:
        if url:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(url)
                r.raise_for_status()
                data = r.json()
        else:
            with open("catalog.json", "r", encoding="utf-8") as f:
                data = json.load(f)
    except Exception as e:
        print(f"[CATALOG] Ошибка загрузки: {e}")
        return False

    CATALOG = data or {"categories": []}
    SKU_INDEX = {}
    for cat in CATALOG.get("categories", []):
        for item in cat.get("items", []):
            if not item.get("available", True):
                continue
            sku = item.get("sku")
            price_rub = float(item.get("price_rub", 0))
            SKU_INDEX[sku] = {
                "sku": sku,
                "title": item.get("title", sku),
                "unit_price_minor": int(round(price_rub * 100)),
                "category_id": cat.get("id"),
                "category_title": cat.get("title", "")
            }
    print(f"[CATALOG] SKU: {len(SKU_INDEX)}; Categories: {len(CATALOG.get('categories', []))}")
    return True
