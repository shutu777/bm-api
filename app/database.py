"""MongoDB 客户端封装。"""

from __future__ import annotations

from pymongo import MongoClient

from .config import settings

client = MongoClient(settings.db_url)
database = client[settings.db_name]

__all__ = ["client", "database"]
