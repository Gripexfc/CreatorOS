import json
import time

from creatoros.services.easel_validation import validate_platform
from creatoros.services.easel_agent_workflow import EaselAgentWorkflowService
from creatoros.services.xhs_constraints import normalize_xhs_metadata, normalize_xhs_title, xhs_title_candidates


def test_overlong_title_has_readable_compliant_choices():
    selected, choices, original = normalize_xhs_title(
        "AI 写小红书总像流水账？这套方法留住人味",
        "第一次用 AI 做小红书内容",
    )
    assert original.startswith("AI 写小红书")
    assert 1 <= len(selected) <= 20
    assert choices
    assert all(1 <= len(choice) <= 20 for choice in choices)


def test_text_only_xhs_validation_does_not_claim_images(tmp_path):
    (tmp_path / "note.md").write_text("# 仅文案\n\n正文只保留作者给出的事实。", encoding="utf-8")
    (tmp_path / "meta.json").write_text(json.dumps({
        "title": "仅文案交付", "platform": "小红书", "created_at": "2026-10-17T10:00:00+08:00",
        "caption": "正文只保留作者给出的事实。" * 30,
        "hashtags": ["#AI", "#写作", "#复盘", "#方法"],
        "post_format": "text", "card_count": 0, "cards": [], "images": [],
        "content_status": "draft", "published": False, "media_status": "text_only",
    }, ensure_ascii=False), encoding="utf-8")
    report = validate_platform("xiaohongshu", tmp_path, tmp_path, output_kind="text")
    assert report["status"] == "passed", report
    assert report["media_kind"] == "copy"
    assert {item["name"] for item in report["checks"]} >= {"xhs_title", "xhs_meta_text", "xhs_media"}


def test_xhs_metadata_caps_provider_hashtags_to_validator_limit():
    normalized = normalize_xhs_metadata({
        "title": "话题数量验收",
        "hashtags": [f"#话题{index}" for index in range(1, 10)],
    })

    assert normalized["hashtags"] == [f"#话题{index}" for index in range(1, 9)]


def test_full_graphic_without_image_provider_is_blocked(tmp_path, monkeypatch):
    monkeypatch.delenv("IMG_BASE_URL", raising=False)
    monkeypatch.delenv("IMG_API_KEY", raising=False)
    service = EaselAgentWorkflowService(tmp_path, lambda: False, lambda *_args, **_kwargs: "")
    try:
        job_id = service.start("完整图文回归", ["xiaohongshu"], output_kind="image")["id"]
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            job = service.get(job_id)
            if job["status"] not in {"queued", "running"}:
                break
            time.sleep(0.01)
        assert job["status"] == "blocked"
        output = job["platform_outputs"]["xiaohongshu"]
        assert output["status"] == "blocked"
        assert "独立生图" in output["missing"][0]
    finally:
        service.executor.shutdown()
