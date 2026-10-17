"""Easel Agent orchestration tests; no model, browser, publisher or network is used."""
from __future__ import annotations

import time
import threading
import json
from pathlib import Path

import creatoros.services.easel_agent_workflow as workflow_module
from creatoros.services.easel_agent_workflow import EaselAgentWorkflowService


def _wait(service, job_id):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        job = service.get(job_id)
        if job["status"] not in {"queued", "running"} and job_id not in service.active:
            return job
        time.sleep(0.01)
    raise AssertionError("easel agent workflow did not settle")


def test_easel_agent_platform_receipt_is_completion_evidence(tmp_path, monkeypatch):
    def validate(platform, directory, skills_root, output_kind="standard"):
        return {
            "status": "passed",
            "checks": [{"name": "fixture-check", "status": "passed"}],
            "missing": [],
            "artifacts": ["main.md"],
            "primary_text": "main.md",
            "copy_text": "可复制内容",
            "media_kind": "script" if platform == "douyin" else "article",
        }

    monkeypatch.setattr(workflow_module, "validate_platform", validate)

    def agent(prompt, timeout, session_id):
        job_id = session_id.split("-")[1]
        folder = tmp_path / f"workflow-{job_id}"
        if "发现与核验" in prompt:
            path = folder / "01-discovery.md"
        elif "选题与结构" in prompt:
            path = folder / "02-topic.md"
        elif "母稿" in prompt:
            path = folder / "03-master.md"
        elif "抖音" in prompt:
            path = folder / "douyin" / "main.md"
        elif "公众号" in prompt:
            path = folder / "wechat-oa" / "main.md"
        elif "质量检查" in prompt:
            path = folder / "05-quality.md"
        else:
            path = folder / "06-archive-checklist.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture", encoding="utf-8")
        return {"response": '{"status":"completed"}', "trace": {"available": True, "skills_read": ["fixture"]}}

    service = EaselAgentWorkflowService(tmp_path, lambda: True, agent)
    try:
        job_id = service.start("主题", ["douyin", "wechat-oa"])["id"]
        job = _wait(service, job_id)
        assert job["status"] == "completed"
        assert job["execution_mode"] == "easel-agent-v1"
        assert all(item["status"] == "completed" for item in job["platform_outputs"].values())
        assert job["platform_outputs"]["douyin"]["primary_text"].endswith("/douyin/main.md")
        assert job["platform_outputs"]["douyin"]["copy_text"] == "可复制内容"
        assert any(item["trace"]["available"] for item in job["execution_receipts"])
        assert job_id not in service.active
    finally:
        service.executor.shutdown()


def test_easel_agent_stage_watchdog_blocks_without_progress(tmp_path):
    def stalled_agent(_prompt, _timeout, _session_id):
        time.sleep(10)
        return 'late response'

    service = EaselAgentWorkflowService(
        tmp_path, lambda: True, stalled_agent,
        stage_timeouts={'discovery': 3}, progress_timeouts={'discovery': 1},
    )
    try:
        job_id = service.start('主题', ['douyin'])['id']
        job = _wait(service, job_id)
        assert job['status'] == 'blocked'
        assert job['stages']['discovery']['status'] == 'blocked'
        assert '没有模型输出或 Agent 事件' in job['stages']['discovery']['reason']
        assert job['stages']['topic']['status'] == 'pending'
    finally:
        service.executor.shutdown(wait=False)


def test_easel_agent_prompt_includes_stage_budget_contract(tmp_path):
    service = EaselAgentWorkflowService(tmp_path, lambda: True, lambda *_args: "ok")
    job = {
        "id": "abc", "topic": "主题", "profile": "读者是个人开发者",
        "context": "作者记录：模型接入失败后修复；不得补写结果。",
        "input_type": "notes", "source": "测试素材", "source_url": "https://example.com/source",
        "platforms": ["wechat-oa"],
    }
    discovery = service._agent_prompt(job, "discovery")
    topic = service._agent_prompt(job, "topic")
    assert "最多核验 3 个一手来源" in discovery
    assert "每个 Skill 最多执行一次" in topic
    assert "作者记录：模型接入失败后修复" in discovery
    assert "https://example.com/source" in topic
    assert "读者是个人开发者" in topic


def test_wechat_materialization_normalizes_markdown_tokens(tmp_path):
    service = EaselAgentWorkflowService(tmp_path, lambda: True, lambda *_args: "ok")
    platform_dir = tmp_path / "wechat-oa"
    receipt = {
        "title": "标题",
        "digest": "摘要",
        "article_markdown": "**第一段**\n\n第二段",
        "html_section": '<section><p><span leaf="">**第一段**</span></p></section>',
        "images": [],
    }
    try:
        assert service._materialize_adaptation_payload("wechat-oa", platform_dir, receipt)
        html = (platform_dir / "article.html").read_text(encoding="utf-8")
        assert "**" not in html
        assert '<span leaf="">第一段</span>' in html
    finally:
        service.executor.shutdown()


def test_structured_platform_fallback_materializes_manual_xhs_and_douyin(tmp_path):
    service = EaselAgentWorkflowService(tmp_path, lambda: True, lambda *_args: "ok")
    try:
        xhs_dir = tmp_path / "xiaohongshu"
        assert service._materialize_adaptation_payload("xiaohongshu", xhs_dir, {
            "title": "一周复盘",
            "caption": "只基于已提供素材的本地草稿，不包含外部数据或发布结果。" * 3,
            "hashtags": ["#AI", "#复盘", "#内容", "#工作流", "#个人开发"],
            "cards": [
                {"type": "cover", "title": "一周复盘", "content": "先把事实列出来"},
                {"type": "content", "title": "第二步", "content": "再标记待核验项"},
                {"type": "ending", "title": "收尾", "content": "最后人工确认"},
            ],
            "images": [],
            "note_markdown": "一周复盘\n\n只基于已提供素材。",
        })
        assert (xhs_dir / "note.md").is_file()
        assert json.loads((xhs_dir / "meta.json").read_text(encoding="utf-8"))["images"] == []
        assert not list(xhs_dir.glob("*.png"))

        douyin_dir = tmp_path / "douyin"
        assert service._materialize_adaptation_payload("douyin", douyin_dir, {
            "title": "一周复盘",
            "script_markdown": "脚本文字草稿",
            "caption": "",
            "hashtags": [],
            "hooks": [],
            "shots": [],
        })
        assert (douyin_dir / "script.md").is_file()
        assert json.loads((douyin_dir / "meta.json").read_text(encoding="utf-8"))["shots"] == []
        assert not list(douyin_dir.glob("*.mp4"))
    finally:
        service.executor.shutdown()


def test_easel_agent_promotes_stable_artifact_before_runner_returns(tmp_path):
    cancelled = []
    entered = threading.Event()

    def agent(prompt, _timeout, _session_id):
        entered.set()
        path = tmp_path / "workflow-job" / "01-discovery.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# 发现与核验\n\n来源：本地验证。\n\n待核验：BLOCKED 的外部来源。" * 20, encoding="utf-8")
        time.sleep(10)
        return "late response"

    service = EaselAgentWorkflowService(tmp_path, lambda: True, agent, agent_canceller=lambda sid: cancelled.append(sid),
                                        stage_timeouts={"discovery": 10}, progress_timeouts={"discovery": 10})
    try:
        path = tmp_path / "workflow-job" / "01-discovery.md"
        result = service._call_agent("prompt", "workflow-job-discovery-attempt-1", timeout=5,
                                     artifact_path=path, artifact_minimum_chars=500,
                                     artifact_markers=("发现与核验", "BLOCKED", "来源"))
        assert "发现与核验" in result
        assert entered.is_set()
        assert cancelled == ["workflow-job-discovery-attempt-1"]
    finally:
        service.executor.shutdown(wait=False)


def test_easel_agent_cancel_terminates_current_session_and_is_retryable(tmp_path):
    entered = threading.Event()
    cancelled = []

    def stalled_agent(_prompt, _timeout, _session_id):
        entered.set()
        time.sleep(10)
        return 'late response'

    def cancel_session(session_id):
        cancelled.append(session_id)

    service = EaselAgentWorkflowService(
        tmp_path, lambda: True, stalled_agent,
        agent_canceller=cancel_session, cancel_runner=cancel_session,
        stage_timeouts={'discovery': 10}, progress_timeouts={'discovery': 10},
    )
    try:
        job_id = service.start('主题', ['douyin'])['id']
        assert entered.wait(1)
        stopped = service.cancel(job_id)
        assert stopped['status'] == 'interrupted'
        job = _wait(service, job_id)
        assert job['status'] == 'interrupted'
        assert job['stages']['discovery']['status'] == 'interrupted'
        assert '用户停止了工作流' in job['stages']['discovery']['reason']
        assert cancelled and cancelled[0].startswith(f'workflow-{job_id}-discovery-')
    finally:
        service.executor.shutdown(wait=False)
