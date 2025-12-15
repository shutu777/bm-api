"""FastAPI 入口。"""

from __future__ import annotations

import logging
from functools import lru_cache

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

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
