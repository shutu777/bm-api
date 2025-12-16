"""
AVBase 爬虫工具：抓取 https://www.avbase.net/works 的搜索页面，只解析前五个卡片，输出番号、标题与演员列表。
"""
from __future__ import annotations

import logging
from typing import Iterable, List, Optional, Set

import requests
from bs4 import BeautifulSoup, Tag

try:  # pragma: no cover - 可选依赖
    import cloudscraper
except ImportError:  # pragma: no cover - 可选依赖
    cloudscraper = None

logger = logging.getLogger("avbase")

BASE_URL = "https://www.avbase.net/works"
TIMEOUT = 15
MAX_RESULTS = 5
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,"
        "image/webp,image/apng,*/*;q=0.8"
    ),
    "Referer": "https://www.avbase.net/works",
    "Cache-Control": "no-cache",
}


def _create_session() -> requests.Session:
    if cloudscraper is not None:
        session = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False}
        )
    else:
        session = requests.Session()
    session.headers.update(HEADERS)
    return session


def _has_required_outer_classes(classes: Optional[Iterable[str]]) -> bool:
    """
    网格容器通常包含 `grid` 与 `gap-4`，只要满足这两个类名即可视为有效，避免 Tailwind 的动态类导致解析失败。
    """
    if not classes:
        return False
    if isinstance(classes, str):
        classes = classes.split()
    return {"grid", "gap-4"}.issubset(set(classes))


def _extract_actor_names(card: Tag) -> List[str]:
    chips = card.select("div.bg-base-100 a.chip")
    actors: List[str] = []
    for chip in chips:
        name = chip.get_text(strip=True)
        if name:
            actors.append(name)
    return actors


def _extract_code(card: Tag) -> str:
    code_tag = card.select_one("span.font-bold.text-gray-500")
    return code_tag.get_text(strip=True) if code_tag else "UNKNOWN"


def _extract_title(card: Tag) -> str:
    title_tag = card.select_one("a.text-md.font-bold")
    return title_tag.get_text(strip=True) if title_tag else ""


def _parse_cards(html: str) -> List[dict]:
    soup = BeautifulSoup(html, "html.parser")
    grid_container = soup.find("div", class_=_has_required_outer_classes)  # type: ignore[arg-type]
    if grid_container is None:
        logger.info("AVBase 页面未找到结果网格，视为无结果。")
        return []

    cards = grid_container.find_all("div", class_="relative", limit=MAX_RESULTS)
    results = []
    for card in cards:
        results.append(
            {
                "code": _extract_code(card),
                "title": _extract_title(card),
                "actors": _extract_actor_names(card),
            }
        )
    return results


def search_avbase(keyword: str) -> List[dict]:
    """
    根据关键字抓取 AVBase，返回包含 code/title/actors 的字典列表。
    """
    keyword = (keyword or "").strip()
    if not keyword:
        return []

    session = _create_session()
    # 未安装 Cloudscraper 时，先访问一次基础页面以获取必要 Cookie。
    if cloudscraper is None:
        try:
            session.get(BASE_URL, timeout=TIMEOUT)
        except requests.RequestException as exc:
            logger.debug("初始化 AVBase 会话失败，但继续执行：%s", exc)

    response = session.get(
        BASE_URL,
        params={"q": keyword},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    logger.info("已完成 AVBase 抓取，关键字=%s", keyword)
    return _parse_cards(response.text)


def is_code_like(keyword: str) -> bool:
    """
    判断关键字是否类似番号（仅包含字母/数字，可含横线和下划线，必须是 ASCII）。
    """
    if not keyword:
        return False
    stripped = "".join(ch for ch in keyword if not ch.isspace())
    if not stripped:
        return False
    sanitized = stripped.replace("-", "").replace("_", "")
    return sanitized.isascii() and sanitized.isalnum()


def filter_actor_cards(cards: List[dict], keyword: str) -> List[dict]:
    """
    关键字匹配演员姓名，只保留命中的演员与卡片。
    """
    needle = keyword.strip().lower()
    if not needle:
        return cards
    needle_simple = needle.replace(" ", "")
    filtered_cards: List[dict] = []
    for card in cards:
        names = card.get("actors", [])
        matched = []
        for name in names:
            normalized = name.lower()
            normalized_simple = normalized.replace(" ", "")
            if needle in normalized or (needle_simple and needle_simple in normalized_simple):
                matched.append(name)
        if matched:
            filtered_cards.append({**card, "actors": matched})
    return filtered_cards


def collapse_actor_list(cards: List[dict], limit: int = MAX_RESULTS) -> List[str]:
    """
    将演员列表扁平化并去重，每张卡片只取第一个演员，限制最多 `limit` 个。
    """
    unique: Set[str] = set()
    collapsed: List[str] = []
    for card in cards:
        actors = card.get("actors") or []
        if not actors:
            continue
        first_actor = actors[0]
        normalized = first_actor.strip()
        if not normalized:
            continue
        lower = normalized.lower()
        if lower in unique:
            continue
        unique.add(lower)
        collapsed.append(normalized)
        if len(collapsed) >= limit:
            break
    return collapsed


__all__ = ["search_avbase", "is_code_like", "filter_actor_cards", "collapse_actor_list"]
