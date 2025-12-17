"""搜索逻辑实现。"""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, Iterable, List

from pymongo.collection import Collection

from .config import settings
from .database import database

logger = logging.getLogger("bt-search")


def _build_query(keyword: str) -> Dict[str, Any]:
    escaped = re.escape(keyword)
    pattern = f".*{escaped}.*"
    return {
        "$or": [
            {"title": {"$regex": pattern, "$options": "i"}},
            {"number": {"$regex": pattern, "$options": "i"}},
        ]
    }


def _safe_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return 0


def _compose_title(number: Any, title: Any) -> str:
    parts = [str(part).strip() for part in (number, title) if part]
    return " ".join(parts).strip()


def _is_chinese_collection(collection_name: str) -> bool:
    return collection_name == "hd_chinese_subtitles"


def _document_to_payload(doc: Dict[str, Any], collection_name: str) -> Dict[str, Any]:
    composed_title = _compose_title(doc.get("number"), doc.get("title"))
    download_raw = doc.get("magnet") or doc.get("download_url") or ""
    download_url = str(download_raw) if download_raw else ""
    payload = {
        "id": _safe_int(doc.get("id")),
        "site": "BT",
        "size_mb": 0.0,
        "seeders": 0,
        "title": composed_title,
        "chinese": _is_chinese_collection(collection_name),
        "uc": bool(doc.get("uc", False)),
        "uhd": bool(doc.get("uhd", False) or doc.get("is_uhd", False)),
        "free": bool(doc.get("free", True)),
        "download_url": download_url,
    }
    return payload


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


def _query_collection(collection_name: str, query: Dict[str, Any]) -> List[Dict[str, Any]]:
    collection: Collection = database[collection_name]
    try:
        cursor = collection.find(query)
        docs = list(cursor)
        logger.info("集合 %s 命中 %s 条记录", collection_name, len(docs))
    except Exception as exc:  # pragma: no cover - 依赖真实数据库
        logger.error("查询集合 %s 失败：%s", collection_name, exc)
        return []

    return [_document_to_payload(doc, collection_name) for doc in docs]


def search_in_tables(keyword: str, page: int) -> Dict[str, Any]:
    keyword = keyword.strip()
    if not keyword:
        logger.warning("收到空关键字请求，直接返回空列表")
        return {"total": 0, "data": []}

    page = max(page, 1)
    query = _build_query(keyword)

    logger.info(
        "开始查询，关键字=%s，页码(暂不分页)=%s，涉及集合=%s",
        keyword,
        page,
        settings.search_tables,
    )

    if not settings.search_tables:
        logger.warning("未配置可搜索集合，直接返回空结果")
        return {"total": 0, "data": []}

    aggregated: List[Dict[str, Any]] = []

    batch_size = max(1, settings.search_batch_size)
    batches = list(_chunked_collections(settings.search_tables, batch_size))

    for batch_index, batch in enumerate(batches, start=1):
        logger.info(
            "分批查询 %s/%s，当前集合=%s", batch_index, len(batches), batch
        )
        with ThreadPoolExecutor(max_workers=len(batch)) as executor:
            futures = {
                executor.submit(_query_collection, collection_name, query): collection_name
                for collection_name in batch
            }

            for future in as_completed(futures):
                aggregated.extend(future.result())

    total = len(aggregated)
    logger.info("聚合后总记录=%s，全部返回", total)
    return {"total": total, "data": aggregated}
