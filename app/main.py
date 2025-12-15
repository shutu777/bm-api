"""FastAPI 入口。"""

from __future__ import annotations

import logging
from functools import lru_cache

from fastapi import FastAPI, HTTPException, Query
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


@lru_cache(maxsize=1)
def _log_startup_once() -> bool:
    logger.info("服务启动成功，默认地址：%s", settings.base_url)
    logger.info("默认集合：%s", settings.search_tables)
    return True


@app.on_event("startup")
async def _startup() -> None:
    _log_startup_once()


@app.get("/bt/api")
async def search_get(
    keyword: str = Query(..., min_length=1, description="关键字"),
    page: int = Query(1, ge=1, description="页码"),
):
    try:
        response = search_in_tables(keyword, page)
        return response
    except Exception as exc:  # pragma: no cover - 依赖外部数据库
        logger.exception("GET 请求失败：%s", exc)
        raise HTTPException(status_code=500, detail="查询失败，请查看日志")


@app.post("/bt/api")
async def search_post(request: SearchRequest):
    try:
        response = search_in_tables(request.keyword, request.page)
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
