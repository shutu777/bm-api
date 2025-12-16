"""FastAPI 入口。"""

from __future__ import annotations

import logging
from functools import lru_cache

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .avbase import collapse_actor_list, filter_actor_cards, is_code_like, search_avbase
from .config import settings
from .search import search_in_tables

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("bt-api")

app = FastAPI(
    title="BT 搜索 API",
    description="查询指定 MongoDB 中的 BT 种子记录。",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class SearchRequest(BaseModel):
    keyword: str = Field(..., description="需要匹配的关键字")
    page: int = Field(default=1, ge=1, description="页码（从1开始）")


def _resolve_keyword(*candidates: str | None) -> str:
    for candidate in candidates:
        if candidate and candidate.strip():
            return candidate.strip()
    return ""


@lru_cache(maxsize=1)
def _log_startup_once() -> bool:
    logger.info("服务启动成功，默认地址：%s", settings.display_base_url())
    logger.info("默认集合：%s", settings.search_tables)
    return True


@app.on_event("startup")
async def _startup() -> None:
    _log_startup_once()


@app.get("/api/search")
async def combined_search(
    keyword: str = Query(..., min_length=1, description="搜索的关键字"),
    page: int = Query(1, ge=1, description="BT 搜索的页码"),
):
    normalized_keyword = keyword.strip()
    if not normalized_keyword:
        raise HTTPException(status_code=422, detail="keyword 参数不能为空")

    keyword_is_code = is_code_like(normalized_keyword)
    actor_names: list[str] = []
    try:
        actor_cards = search_avbase(normalized_keyword)
        if not keyword_is_code:
            actor_cards = filter_actor_cards(actor_cards, normalized_keyword)
        actor_names = collapse_actor_list(actor_cards)
    except Exception as exc:  # pragma: no cover - 依赖外部网站
        logger.exception("AVBase 搜索失败：%s", exc)
        return JSONResponse(
            status_code=502,
            content={
                "code": 502,
                "message": "AVBase 搜索失败，请稍后重试",
                "actors": [],
                "torrents": [],
            },
        )

    try:
        torrents_payload = search_in_tables(normalized_keyword, page)
    except Exception as exc:  # pragma: no cover - 依赖外部数据库
        logger.exception("BT 搜索失败：%s", exc)
        return JSONResponse(
            status_code=500,
            content={
                "code": 500,
                "message": "BT 搜索失败，请查看日志",
                "actors": actor_names,
                "torrents": [],
            },
        )

    torrents = []
    if isinstance(torrents_payload, dict):
        torrents = torrents_payload.get("data", [])

    return {"code": 200, "actors": actor_names, "torrents": torrents}


@app.get("/bt/api")
async def search_get(
    keyword: str | None = Query(None, min_length=1, description="关键字"),
    query_keyword: str | None = Query(
        None, alias="query", min_length=1, description="备用参数 query"
    ),
    page: int = Query(1, ge=1, description="页码"),
):
    final_keyword = _resolve_keyword(keyword, query_keyword)
    if not final_keyword:
        raise HTTPException(status_code=422, detail="keyword/query 参数不能为空")

    try:
        response = search_in_tables(final_keyword, page)
        return response
    except Exception as exc:  # pragma: no cover - 依赖外部数据库
        logger.exception("GET 请求失败：%s", exc)
        raise HTTPException(status_code=500, detail="查询失败，请查看日志")


@app.post("/bt/api")
async def search_post(
    request: SearchRequest | None = Body(
        None, description="POST body，keyword/page 字段"
    ),
    keyword_query: str | None = Query(
        None, alias="keyword", min_length=1, description="query 参数 keyword"
    ),
    query_keyword: str | None = Query(
        None, alias="query", min_length=1, description="备用参数 query"
    ),
    page_query: int = Query(
        1, alias="page", ge=1, description="当 body 缺失时使用的页码"
    ),
):
    body_keyword = request.keyword if request else None
    body_page = request.page if request else None

    final_keyword = _resolve_keyword(body_keyword, keyword_query, query_keyword)
    if not final_keyword:
        raise HTTPException(status_code=422, detail="keyword/query 参数不能为空")

    final_page = body_page if body_page is not None else page_query

    try:
        response = search_in_tables(final_keyword, final_page)
        return response
    except Exception as exc:  # pragma: no cover - 依赖外部数据库
        logger.exception("POST 请求失败：%s", exc)
        raise HTTPException(status_code=500, detail="查询失败，请查看日志")


if __name__ == "__main__":  # pragma: no cover - 手动运行
    import uvicorn

    logger.info("以独立进程模式启动 Uvicorn……")
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        log_level="info",
    )
