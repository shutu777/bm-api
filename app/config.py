"""配置管理，全部依赖环境变量。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List


def _split_env_list(value: str | None) -> List[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _int_from_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        number = int(raw)
    except ValueError:
        return default
    return max(number, 1)


@dataclass(slots=True)
class Settings:
    """读取项目运行所需的全部配置。"""

    base_url: str = field(
        default=os.getenv("BASE_URL", "http://192.168.5.5:10000/bt/api")
    )
    api_host: str = field(default=os.getenv("API_HOST", "0.0.0.0"))
    api_port: int = field(default=_int_from_env("API_PORT", 10000))
    db_url: str = field(
        default=os.getenv(
            "DB_URL",
            "mongodb://crawler:crawler_secure_password@192.168.5.5:27017/sehuatang",
        )
    )
    db_name: str = field(default=os.getenv("DB_NAME", "sehuatang"))
    search_tables: List[str] = field(
        default_factory=lambda: _split_env_list(
            os.getenv(
                "SEARCH_TABLES",
                ",".join(
                    [
                        "4k_video",
                        "anime_originate",
                        "asia_codeless_originate",
                        "asia_mosaic_originate",
                        "domestic_original",
                        "hd_chinese_subtitles",
                        "three_levels_photo",
                        "vegan_with_mosaic",
                    ]
                ),
            )
        )
    )
    page_size: int = field(default=_int_from_env("PAGE_SIZE", 20))


settings = Settings()
