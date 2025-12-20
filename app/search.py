"""BT search logic and payload assembly."""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, Iterable, List, Tuple

from pymongo.collection import Collection

from .config import settings
from .database import database

logger = logging.getLogger("bt-search")

SIZE_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*(GB|MB|KB|GIB|MIB|KIB)", re.IGNORECASE)
INVALID_TEXT_VALUES = {"", "none", "null"}
MAGNET_KEYS = ("magnet", "Magnet Links")
TITLE_KEYS = ("title", "Title", "Movie Name")
NUMBER_KEYS = ("number", "Number")
SIZE_KEYS = ("size_mb", "size", "Movie Size")


def _build_query(keyword: str) -> Dict[str, Any]:
    escaped = re.escape(keyword)
    pattern = f".*{escaped}.*"
    return {
        "$or": [
            {"title": {"$regex": pattern, "$options": "i"}},
            {"number": {"$regex": pattern, "$options": "i"}},
        ]
    }


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in INVALID_TEXT_VALUES:
        return ""
    return text


def _first_present(doc: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in doc and doc[key] not in (None, ""):
            return doc[key]
    return None


def _compose_title(number: Any, title: Any, brand_label: str | None = None) -> str:
    number_str = _clean_text(number)
    title_str = _clean_text(title)
    if title_str and brand_label and brand_label not in title_str:
        title_str = f"{brand_label} {title_str}".strip()
    if number_str:
        if title_str:
            if number_str in title_str:
                return title_str
            return f"{number_str} {title_str}".strip()
        return number_str
    return title_str or "No Title"


def _extract_numeric_id(doc: Dict[str, Any]) -> int:
    for key in ("tid", "id"):
        if key in doc:
            try:
                return int(str(doc[key]))
            except (TypeError, ValueError):
                continue
    fallback = doc.get("_id")
    if fallback is None:
        return 0
    try:
        fallback_str = str(fallback)
        return int(fallback_str[-8:], 16)
    except (ValueError, TypeError):
        return 0


def _extract_size_from_text(text: str) -> float:
    if not text:
        return 0.0
    match = SIZE_PATTERN.search(text)
    if not match:
        return 0.0
    try:
        value = float(match.group(1))
    except ValueError:
        return 0.0
    unit = match.group(2).upper()
    if "G" in unit:
        return value * 1024
    if "M" in unit:
        return value
    if "K" in unit:
        return value / 1024
    return 0.0


def _resolve_size_mb(doc: Dict[str, Any], fallback_text: str) -> float:
    for key in SIZE_KEYS:
        if key in doc and doc[key] not in (None, ""):
            try:
                return float(doc[key])
            except (TypeError, ValueError):
                continue
    return _extract_size_from_text(fallback_text)


def _classify(collection_name: str, final_title: str) -> Tuple[bool, bool, bool]:
    name = collection_name.lower()
    is_chinese = "chinese" in name or "domestic" in name
    is_uc = any(
        keyword in name
        for keyword in ("codeless", "domestic", "no_mosaic", "korean", "nomosaic")
    )
    is_uhd = "4k" in name

    title_upper = final_title.upper()
    if "中字" in final_title or re.search(r"[-_]C\b", title_upper):
        is_chinese = True
    if any(keyword in final_title for keyword in ("无码", "破解", "流出")):
        is_uc = True
    if "FC2" in title_upper:
        is_uc = True
    if "4K" in title_upper:
        is_uhd = True

    return is_chinese, is_uc, is_uhd


def _document_to_payload(doc: Dict[str, Any], collection_name: str) -> Dict[str, Any]:
    raw_title = _first_present(doc, *TITLE_KEYS)
    raw_number = _first_present(doc, *NUMBER_KEYS)
    brand_label = "[色花堂]"
    final_title = _compose_title(raw_number, raw_title, brand_label)
    magnet = _clean_text(_first_present(doc, *MAGNET_KEYS))
    size_mb = round(_resolve_size_mb(doc, final_title), 2)
    is_chinese, is_uc, is_uhd = _classify(collection_name, final_title)

    return {
        "id": _extract_numeric_id(doc),
        "site": "Sehuatang",
        "table": collection_name,
        "size_mb": size_mb,
        "seeders": 999,
        "title": final_title,
        "number": _clean_text(raw_number),  # Added for sorting
        "chinese": is_chinese,
        "uc": is_uc,
        "uhd": is_uhd,
        "free": True,
        "download_url": magnet,
    }


def _should_skip_document(
    doc: Dict[str, Any],
    seen_magnets: set[str],  # Local deduplication within collection
    seen_titles: set[str],
) -> Tuple[bool, str, str]:
    magnet = _clean_text(_first_present(doc, *MAGNET_KEYS))
    title = _clean_text(_first_present(doc, *TITLE_KEYS))
    if not magnet:
        return True, "", ""
    if magnet in seen_magnets:
        return True, "", ""
    # Note: Title deduplication within collection logic kept as is
    if title and title in seen_titles:
        return True, "", ""
    return False, magnet, title


def _chunked_collections(
    collections: Iterable[str], chunk_size: int
) -> Iterable[List[str]]:
    chunk: List[str] = []
    for name in collections:
        chunk.append(name)
        if len(chunk) == chunk_size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


def _query_collection(
    collection_name: str,
    query: Dict[str, Any],
) -> List[Dict[str, Any]]:
    collection: Collection = database[collection_name]
    seen_magnets: set[str] = set()
    seen_titles: set[str] = set()
    try:
        cursor = collection.find(query).sort("_id", -1)
        docs = list(cursor)
        logger.info("📂 集合 %s 匹配到 %s 条文档", collection_name, len(docs))
    except Exception as exc:  # pragma: no cover - relies on live MongoDB
        logger.error("❌ 集合 %s 查询失败：%s", collection_name, exc)
        return []

    payloads: List[Dict[str, Any]] = []
    for doc in docs:
        skip, magnet, title = _should_skip_document(doc, seen_magnets, seen_titles)
        if skip:
            continue
        seen_magnets.add(magnet)
        if title:
            seen_titles.add(title)
        payloads.append(_document_to_payload(doc, collection_name))
    return payloads


def search_in_tables(keyword: str, page: int) -> Dict[str, Any]:
    keyword = keyword.strip()
    if not keyword:
        logger.warning("⚠️ 收到空关键字，返回空列表")
        return {"total": 0, "data": []}

    query = _build_query(keyword)

    if not settings.search_tables:
        logger.warning("⚠️ 未配置搜索集合，返回空结果")
        return {"total": 0, "data": []}

    logger.info(
        "🔍 开始 BT 搜索（忽略分页），关键字=%s，请求页码=%s，集合列表=%s",
        keyword,
        page,
        settings.search_tables,
    )

    raw_results: List[Dict[str, Any]] = []
    batch_size = max(1, settings.search_batch_size)
    batches = list(_chunked_collections(settings.search_tables, batch_size))

    for batch_index, batch in enumerate(batches, start=1):
        logger.info(
            "🚀 执行查询批次 %s/%s：%s",
            batch_index,
            len(batches),
            batch,
        )
        with ThreadPoolExecutor(max_workers=len(batch)) as executor:
            futures = {
                executor.submit(
                    _query_collection,
                    collection_name,
                    query,
                ): collection_name
                for collection_name in batch
            }

            for future in as_completed(futures):
                raw_results.extend(future.result())

    # Global deduplication
    global_seen_magnets: set[str] = set()
    unique_results: List[Dict[str, Any]] = []
    
    for item in raw_results:
        magnet = item.get("download_url", "")
        if magnet and magnet not in global_seen_magnets:
            global_seen_magnets.add(magnet)
            unique_results.append(item)
            
    # Global sorting: by 'number' ascending
    # Items with empty number come last (or first? usually empty number is less interesting)
    # Let's put empty number at the end.
    unique_results.sort(key=lambda x: (x.get("number") == "", x.get("number", "").lower()))

    total = len(unique_results)
    logger.info("✅ 全局去重后汇总 %s 条记录，准备返回", total)
    return {"total": total, "data": unique_results}
