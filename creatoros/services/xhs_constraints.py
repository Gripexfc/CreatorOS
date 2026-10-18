"""Deterministic Xiaohongshu delivery constraints shared by workflows."""
from __future__ import annotations

import re
from typing import Any

XHS_TITLE_MAX_LENGTH = 20
XHS_HASHTAG_MAX_COUNT = 8


def _clean_title(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"^\s*#+\s*", "", text)
    text = re.sub(r"^\s*(?:标题|title)\s*[:：]\s*", "", text, flags=re.I)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" \t\r\n#*`_")


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        clean = _clean_title(value)
        if clean and len(clean) <= XHS_TITLE_MAX_LENGTH and clean not in result:
            result.append(clean)
    return result


def xhs_title_candidates(title: Any = "", topic: Any = "") -> list[str]:
    """Return up to three directly usable 1–20 character title choices."""
    raw = _clean_title(title)
    topic_text = _clean_title(topic)
    candidates: list[str] = []
    if raw:
        if len(raw) <= XHS_TITLE_MAX_LENGTH:
            candidates.append(raw)
        # Prefer a complete clause before a hard truncation. This keeps a
        # generated question readable when the provider returned an overlong
        # editorial title.
        for part in re.split(r"[？?!！：:，,。；;、|]", raw):
            part = _clean_title(part)
            if part:
                candidates.append(part)
        candidates.append(raw[:XHS_TITLE_MAX_LENGTH].rstrip(" ，,：:；;。.!！?？"))
    if topic_text:
        candidates.append(topic_text)
        candidates.append(topic_text[:XHS_TITLE_MAX_LENGTH].rstrip(" ，,：:；;。.!！?？"))
    # This fallback is intentionally generic but truthful; it is only reached
    # when the model omitted a title and the user has no usable topic.
    candidates.append("小红书写作方法")
    return _dedupe(candidates)[:3]


def normalize_xhs_title(title: Any = "", topic: Any = "") -> tuple[str, list[str], str]:
    """Return (selected_title, candidates, original_title)."""
    original = _clean_title(title)
    candidates = xhs_title_candidates(original, topic)
    return candidates[0], candidates, original


def normalize_xhs_metadata(meta: dict[str, Any], topic: Any = "") -> dict[str, Any]:
    """Apply deterministic Xiaohongshu title and hashtag constraints."""
    normalized = dict(meta)
    selected, candidates, original = normalize_xhs_title(meta.get("title"), topic)
    normalized["title"] = selected
    normalized["title_candidates"] = candidates
    if original and original != selected:
        normalized["title_original"] = original
    hashtags = meta.get("hashtags")
    if isinstance(hashtags, list):
        normalized["hashtags"] = [
            item.strip() for item in hashtags
            if isinstance(item, str) and item.strip()
        ][:XHS_HASHTAG_MAX_COUNT]
    return normalized
