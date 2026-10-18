from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
from threading import Lock
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen


# The same public hot-list sources used by Easel. Publishing destinations are
# independent of these discovery sources.
TREND_SOURCES: Dict[str, Tuple[str, Tuple[Tuple[str, str], ...]]] = {
    "douyin": ("抖音", (("60秒热榜", "https://60s.viki.moe/v2/douyin"), ("XXAPI 热榜（备用）", "https://v2.xxapi.cn/api/douyinhot"))),
    "weibo": ("微博", (("60秒热榜", "https://60s.viki.moe/v2/weibo"), ("XXAPI 热榜（备用）", "https://v2.xxapi.cn/api/weibohot"))),
    "zhihu": ("知乎", (("60秒热榜", "https://60s.viki.moe/v2/zhihu"),)),
    "bilibili": ("哔哩哔哩", (("60秒热榜", "https://60s.viki.moe/v2/bili"), ("XXAPI 热榜（备用）", "https://v2.xxapi.cn/api/bilibilihot"))),
    "baidu": ("百度", (("60秒热榜", "https://60s.viki.moe/v2/baidu/hot"), ("XXAPI 热榜（备用）", "https://v2.xxapi.cn/api/baiduhot"))),
    "toutiao": ("今日头条", (("60秒热榜", "https://60s.viki.moe/v2/toutiao"),)),
}
REFRESH_SECONDS = 300


def _decode_json(raw: bytes) -> Any:
    if len(raw) > 2_000_000:
        raise ValueError("热榜响应过大")
    return json.loads(raw.decode("utf-8-sig"))


def _fetch_json_with_curl(url: str) -> Any:
    result = subprocess.run(
        [
            "curl.exe",
            "--ssl-no-revoke",
            "--fail",
            "--location",
            "--silent",
            "--show-error",
            "--max-time",
            "7",
            "-H",
            "User-Agent: CreatorOS/0.1",
            "-H",
            "Accept: application/json",
            "--",
            url,
        ],
        capture_output=True,
        check=True,
        timeout=10,
    )
    return _decode_json(result.stdout)


def fetch_json(url: str) -> Any:
    request = Request(url, headers={"User-Agent": "CreatorOS/0.1", "Accept": "application/json"})
    try:
        with urlopen(request, timeout=7) as response:
            return _decode_json(response.read(2_000_001))
    except Exception:
        # Some Windows networks cannot reach certificate-revocation servers,
        # causing Schannel to reject otherwise reachable public feeds. The
        # Windows launch/task scripts opt into the system curl fallback; other
        # environments keep normal certificate verification only.
        if os.name != "nt" or os.getenv("CREATOROS_CURL_NO_REVOKE", "").lower() not in {"1", "true", "yes"}:
            raise
        return _fetch_json_with_curl(url)


def _text(value: Any) -> str:
    return str(value).strip() if isinstance(value, (str, int, float)) and not isinstance(value, bool) else ""


def _first_text(item: Dict[str, Any], keys: Tuple[str, ...]) -> str:
    return next((value for key in keys if (value := _text(item.get(key)))), "")


def _search_url(platform: str, title: str) -> str:
    encoded = quote(title, safe="")
    prefixes = {
        "douyin": "https://www.douyin.com/search/",
        "weibo": "https://s.weibo.com/weibo?q=",
        "zhihu": "https://www.zhihu.com/search?type=content&q=",
        "bilibili": "https://search.bilibili.com/all?keyword=",
        "baidu": "https://www.baidu.com/s?wd=",
        "toutiao": "https://so.toutiao.com/search?keyword=",
    }
    return prefixes[platform] + encoded


def _safe_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        return bool(
            parsed.scheme in {"http", "https"}
            and parsed.hostname
            and not parsed.username
            and not parsed.password
            and not any(ord(char) < 33 for char in value)
        )
    except ValueError:
        return False


def parse_items(payload: Any, platform: str) -> List[Dict[str, Any]]:
    """Normalize primary and fallback feeds without inventing heat or facts."""
    rows = payload
    # Providers use either data: [], data: {list: []}, or data: {data: []}.
    for _ in range(3):
        if isinstance(rows, list):
            break
        if not isinstance(rows, dict):
            return []
        rows = rows.get("data", rows.get("list"))
    if not isinstance(rows, list):
        return []
    normalized: List[Dict[str, Any]] = []
    seen = set()
    for rank, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            continue
        title = _first_text(row, ("title", "word", "name")).strip()[:300]
        if not title or title.casefold() in seen:
            continue
        seen.add(title.casefold())
        source_url = _first_text(row, ("url", "link", "mobil_url", "mobile_url"))
        is_search = not _safe_url(source_url)
        summary = _first_text(row, ("summary", "description", "desc", "excerpt"))[:2000]
        if is_search:
            source_url = _search_url(platform, title)
            summary = (summary + "\n" if summary else "") + "来源未提供可用原文链接，打开的是平台搜索页。"
        normalized.append({
            "id": platform + "-" + hashlib.sha256(title.casefold().encode("utf-8")).hexdigest()[:20],
            "title": title,
            "hot": _first_text(row, ("hot_value_desc", "hot_value", "hot", "score", "num"))[:100],
            "url": source_url,
            "rank": rank,
            "summary": summary,
        })
        if len(normalized) >= 30:
            break
    return normalized


class TrendService:
    """Fetch each source independently, keeping a timestamped last good result."""

    def __init__(
        self,
        fetcher: Optional[Callable[[str], Any]] = None,
        clock: Callable[[], float] = time.monotonic,
        cache_path: Optional[Path] = None,
    ):
        self._fetcher = fetcher or fetch_json
        self._clock = clock
        self._cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
        self._locks = {platform: Lock() for platform in TREND_SOURCES}
        self._cache_path = Path(cache_path) if cache_path else None
        self._cache_state_lock = Lock()
        self._cache_file_lock = Lock()
        self._cache_mtime_ns: Optional[int] = None
        self._load_persisted_cache()

    def _load_persisted_cache(self) -> None:
        if self._cache_path is None or not self._cache_path.is_file():
            return
        try:
            mtime_ns = self._cache_path.stat().st_mtime_ns
            with self._cache_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            feeds = payload.get("feeds", {}) if isinstance(payload, dict) else {}
            if not isinstance(feeds, dict):
                return
            now = self._clock()
            wall_now = time.time()
            loaded: Dict[str, Tuple[float, Dict[str, Any]]] = {}
            for platform, entry in feeds.items():
                if platform not in TREND_SOURCES or not isinstance(entry, dict):
                    continue
                result = entry.get("result")
                cached_at = entry.get("cached_at")
                if not isinstance(result, dict) or not isinstance(cached_at, (int, float)):
                    continue
                age = max(0.0, wall_now - float(cached_at))
                loaded[platform] = (now - age, result)
            with self._cache_state_lock:
                self._cache.update(loaded)
            self._cache_mtime_ns = mtime_ns
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            # A damaged or partially written cache must never prevent the API
            # from starting; the next successful fetch will replace it.
            return

    def _reload_persisted_cache_if_changed(self) -> None:
        if self._cache_path is None or not self._cache_path.is_file():
            return
        try:
            mtime_ns = self._cache_path.stat().st_mtime_ns
        except OSError:
            return
        if self._cache_mtime_ns is None or mtime_ns > self._cache_mtime_ns:
            self._load_persisted_cache()

    def _persist_cache(self) -> None:
        if self._cache_path is None:
            return
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            with self._cache_file_lock:
                with self._cache_state_lock:
                    feeds = {
                        platform: {"cached_at": time.time(), "result": result}
                        for platform, (_cached_at, result) in self._cache.items()
                    }
                payload = {
                    "version": 1,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "feeds": feeds,
                }
                temporary = self._cache_path.with_suffix(self._cache_path.suffix + ".tmp")
                with temporary.open("w", encoding="utf-8") as handle:
                    json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
                os.replace(temporary, self._cache_path)
                self._cache_mtime_ns = self._cache_path.stat().st_mtime_ns
        except OSError:
            # Cache persistence is an optimization. Live fetching should keep
            # working when a read-only or locked runtime directory is used.
            return

    def _platform(self, platform: str, refresh: bool) -> Dict[str, Any]:
        label, sources = TREND_SOURCES[platform]
        with self._locks[platform]:
            with self._cache_state_lock:
                cached = self._cache.get(platform)
            if cached and not refresh and self._clock() - cached[0] < REFRESH_SECONDS:
                return {**cached[1], "status": "cached"}
            for source_name, source_url in sources:
                try:
                    items = parse_items(self._fetcher(source_url), platform)
                    if not items:
                        continue
                    result = {
                        "platform": platform,
                        "label": label,
                        "status": "fresh",
                        "fetched_at": datetime.now(timezone.utc).isoformat(),
                        "source_name": source_name,
                        "source_url": source_url,
                        "error": None,
                        "items": items,
                    }
                    with self._cache_state_lock:
                        self._cache[platform] = (self._clock(), result)
                    self._persist_cache()
                    return result
                except Exception:
                    # A provider failure must not break other platforms. Avoid
                    # returning request internals or misleading fresh timestamps.
                    continue
            error = "暂时无法获取最新热榜，请稍后重试。"
            if cached:
                return {**cached[1], "status": "stale", "error": error + "当前显示上次成功获取的数据。"}
            return {
                "platform": platform, "label": label, "status": "unavailable",
                "fetched_at": None, "source_name": None, "source_url": None,
                "error": error, "items": [],
            }

    def get_trends(self, platforms: List[str], limit: int = 12, refresh: bool = False) -> Dict[str, Any]:
        self._reload_persisted_cache_if_changed()
        platforms = list(dict.fromkeys(platforms))
        if not platforms or any(platform not in TREND_SOURCES for platform in platforms):
            raise ValueError("不支持的热榜来源")
        if not 1 <= limit <= 30:
            raise ValueError("热榜条数必须为 1–30")
        with ThreadPoolExecutor(max_workers=len(platforms)) as pool:
            results = list(pool.map(lambda platform: self._platform(platform, refresh), platforms))
        return {
            "trends": [{**result, "items": result["items"][:limit]} for result in results],
            "refresh_after_seconds": REFRESH_SECONDS,
        }
