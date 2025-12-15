"""配置管理，全部依赖环境变量。"""

from __future__ import annotations

import os
import shutil
import socket
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
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


def _detect_git_root_parts() -> tuple[str, ...] | None:
    git_binary = shutil.which("git")
    if not git_binary:
        return None
    root_path = Path(git_binary).resolve().parent.parent
    return PurePosixPath(root_path.as_posix()).parts


_GIT_ROOT_PARTS = _detect_git_root_parts()
_GIT_ROOT_PARTS_LOWER = (
    tuple(part.lower() for part in _GIT_ROOT_PARTS) if _GIT_ROOT_PARTS else None
)


def _normalize_base_path(value: str | None) -> str:
    if not value:
        return "/bt/api"
    value = value.strip()
    if not value:
        return "/bt/api"
    if value.startswith("http://") or value.startswith("https://"):
        return value.rstrip("/")
    normalized = value.replace("\\", "/")
    if ":" in normalized and not normalized.startswith("//"):
        parts = PurePosixPath(normalized).parts
        if parts and parts[0].endswith(":"):
            lower_parts = tuple(part.lower() for part in parts)
            if (
                _GIT_ROOT_PARTS_LOWER
                and lower_parts[: len(_GIT_ROOT_PARTS_LOWER)] == _GIT_ROOT_PARTS_LOWER
            ):
                parts = parts[len(_GIT_ROOT_PARTS_LOWER) :]
            else:
                parts = parts[1:]
            normalized = "/" + "/".join(parts)
    if not normalized.startswith("/"):
        normalized = "/" + normalized.lstrip("/")
    while "//" in normalized:
        normalized = normalized.replace("//", "/")
    return normalized.rstrip("/") or "/"


def _determine_public_host(api_host: str) -> str:
    env_host = os.getenv("PUBLIC_HOST")
    if env_host:
        return env_host
    if api_host not in {"0.0.0.0", "127.0.0.1"}:
        return api_host
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
        return ip
    except OSError:
        return api_host


@dataclass(slots=True)
class Settings:
    """读取项目运行所需的全部配置。"""

    base_url: str = field(default=_normalize_base_path(os.getenv("BASE_URL")))
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

    def display_base_url(self) -> str:
        base = self.base_url
        if base.startswith("http://") or base.startswith("https://"):
            return base
        host = _determine_public_host(self.api_host)
        return f"http://{host}:{self.api_port}{base}"


settings = Settings()
