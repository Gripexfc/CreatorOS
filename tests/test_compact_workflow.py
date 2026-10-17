"""Compact-v2 workflow tests; no real model, network, or publisher is used."""
import json
import time

from creatoros.services.workflow_service import FINAL_ARTIFACTS, WorkflowService


def wait_job(service, job_id):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        job = service.get(job_id)
        if job['status'] not in {'queued', 'running'} and job_id not in service.active:
            return job
        time.sleep(0.01)
    raise AssertionError('compact workflow did not settle')


def test_compact_uses_one_research_and_one_compose_call(tmp_path):
    calls = []

    def research(prompt, session_id):
        calls.append((session_id, prompt))
        return '事实：官方公告；来源：https://example.com；待核验：热度。'

    def compose(prompt, session_id):
        calls.append((session_id, prompt))
        return {'platform': 'xiaohongshu', 'content': '小红书终稿\n事实边界已保留。'}

    service = WorkflowService(tmp_path, lambda: True, research, compose_runner=compose)
    try:
        job_id = service.start('主题', ['xiaohongshu'])['id']
        job = wait_job(service, job_id)
        assert job['status'] == 'completed'
        assert job['execution_mode'] == 'compact-v2'
        assert [item[0] for item in calls] == [
            f'workflow-{job_id}-compact-research-attempt-1',
            f'workflow-{job_id}-compact-compose-xiaohongshu-attempt-1',
        ]
        final = tmp_path / f'workflow-{job_id}' / FINAL_ARTIFACTS['xiaohongshu']
        assert final.read_text(encoding='utf-8').startswith('小红书终稿')
        assert job['stages']['quality']['status'] == 'completed'
        quality = (tmp_path / job['stages']['quality']['artifact']).read_text(encoding='utf-8')
        assert '需人工复核' in quality
        assert '平台门禁风险' in quality
    finally:
        service.executor.shutdown()


def test_compact_persists_and_injects_original_material_and_profile(tmp_path):
    prompts = []

    def research(prompt, _session_id):
        prompts.append(prompt)
        return '研究简报\n来源：https://example.com\n待核验：无'

    def compose(prompt, _session_id):
        prompts.append(prompt)
        return {'platform': 'xiaohongshu', 'content': '小红书终稿\n只使用已给事实。'}

    service = WorkflowService(tmp_path, lambda: True, research, compose_runner=compose)
    try:
        job_id = service.start(
            '一周复盘如何避免空话', ['xiaohongshu'],
            profile='读者是 AI 入门的个人开发者；语气直接，避免夸大',
            context='我记录了模型接入失败和修复过程；没有公开数据，不得补写结果。',
            input_type='notes', source='作者测试素材', source_url='https://example.com/source',
        )['id']
        job = wait_job(service, job_id)
        assert job['context'].startswith('我记录了模型接入失败')
        assert job['input_type'] == 'notes'
        assert job['source'] == '作者测试素材'
        assert job['source_url'] == 'https://example.com/source'
        assert all('我记录了模型接入失败' in prompt for prompt in prompts)
        assert all('读者是 AI 入门的个人开发者' in prompt for prompt in prompts)
        assert all('https://example.com/source' in prompt for prompt in prompts)
    finally:
        service.executor.shutdown()


def test_compact_materializes_wechat_platform_receipt(tmp_path):
    def research(_prompt, _session_id):
        return '研究简报\n来源：合成验收素材'

    def compose(_prompt, session_id):
        return {'platform': 'wechat-oa', 'content': '自动生成不等于可发布\n\n失败节点与读者动作已分开记录。'}

    service = WorkflowService(tmp_path, lambda: True, research, compose_runner=compose)
    try:
        job_id = service.start('自动生成内容验收', ['wechat-oa'], context='模型接入失败；不得补写收益。', input_type='notes')['id']
        job = wait_job(service, job_id)
        assert job['status'] == 'completed'
        output = job['platform_outputs']['wechat-oa']
        assert output['status'] == 'passed'
        platform_dir = tmp_path / f'workflow-{job_id}' / 'wechat-oa'
        assert (platform_dir / 'article.md').is_file()
        assert (platform_dir / 'article.html').is_file()
        assert (platform_dir / 'meta.json').is_file()
        assert output['primary_text'].endswith('/wechat-oa/article.md')
    finally:
        service.executor.shutdown()


def test_compact_retry_preserves_research_and_only_retries_failed_platform(tmp_path):
    research_calls = 0
    compose_calls = []

    def research(_prompt, _session_id):
        nonlocal research_calls
        research_calls += 1
        return '共享研究\n来源：https://example.com'

    def compose(_prompt, session_id):
        compose_calls.append(session_id)
        if 'douyin' in session_id and 'attempt-1' in session_id:
            raise RuntimeError('模型请求超时')
        platform = 'xiaohongshu' if 'xiaohongshu' in session_id else 'douyin'
        return {'platform': platform, 'content': f'{platform} 终稿'}

    service = WorkflowService(tmp_path, lambda: True, research, compose_runner=compose)
    try:
        job_id = service.start('主题', ['xiaohongshu', 'douyin'])['id']
        failed = wait_job(service, job_id)
        assert failed['status'] == 'failed'
        assert research_calls == 1
        assert (tmp_path / f'workflow-{job_id}' / FINAL_ARTIFACTS['xiaohongshu']).is_file()

        service.retry(job_id)
        done = wait_job(service, job_id)
        assert done['status'] == 'completed'
        assert research_calls == 1
        assert len([x for x in compose_calls if 'xiaohongshu' in x]) == 1
        assert len([x for x in compose_calls if 'douyin' in x]) == 2
    finally:
        service.executor.shutdown()


def test_explicit_retry_migrates_failed_legacy_job_when_compose_is_available(tmp_path):
    legacy_calls = []

    def legacy(prompt):
        legacy_calls.append(prompt)
        if '阶段：主稿' in prompt:
            raise RuntimeError('模型请求超时')
        return '旧研究产物'

    def compose(_prompt, _session_id):
        return {'platform': 'wechat-oa', 'content': '恢复后的公众号终稿'}

    service = WorkflowService(tmp_path, lambda: True, legacy)
    try:
        job_id = service.start('主题', ['wechat-oa'])['id']
        failed = wait_job(service, job_id)
        assert failed['status'] == 'failed'
        discovery = tmp_path / failed['stages']['discovery']['artifact']
        service.compose_runner = compose
        service.retry(job_id)
        done = wait_job(service, job_id)
        assert done['status'] == 'completed'
        assert done['execution_mode'] == 'compact-v2'
        assert done['migrated_from'] == 'legacy-v1'
        assert discovery.read_text(encoding='utf-8') == '旧研究产物'
    finally:
        service.executor.shutdown()


def test_compact_streaming_preview_is_checkpointed_and_completed(tmp_path):
    def research(_prompt, _session_id):
        return '共享研究\n来源：https://example.com'

    def compose(_prompt, _session_id):
        return {'platform': 'xiaohongshu', 'content': '完整终稿'}

    def stream_compose(_prompt, _session_id, on_delta):
        on_delta('实时')
        on_delta('预览')
        return {'platform': 'xiaohongshu', 'content': '完整终稿'}

    service = WorkflowService(
        tmp_path, lambda: True, research,
        compose_runner=compose, compose_stream_runner=stream_compose,
    )
    try:
        job_id = service.start('主题', ['xiaohongshu'])['id']
        job = wait_job(service, job_id)
        assert job['status'] == 'completed'
        preview = job['streaming_outputs']['xiaohongshu']
        assert preview['text'] == '完整终稿'
        assert preview['complete'] is True
        assert preview['chars'] == len('完整终稿')
    finally:
        service.executor.shutdown()


def test_compact_retry_materializes_manual_handoffs_without_fake_media(tmp_path):
    def research(_prompt, _session_id):
        return '共享研究\n来源：https://example.com'

    def compose(_prompt, session_id):
        platform = 'xiaohongshu' if 'xiaohongshu' in session_id else 'douyin'
        return {
            'platform': platform,
            'content': f'{platform} 真实草稿\n\n只包含当前输入事实，媒体需要人工补齐。',
        }

    service = WorkflowService(tmp_path, lambda: True, research, compose_runner=compose)
    try:
        job_id = service.start('主题', ['xiaohongshu', 'douyin'])['id']
        job = wait_job(service, job_id)
        assert job['status'] == 'completed'
        folder = tmp_path / f'workflow-{job_id}'
        for platform, source in (('xiaohongshu', 'note.md'), ('douyin', 'script.md')):
            platform_dir = folder / platform
            assert (platform_dir / source).is_file()
            assert (platform_dir / 'meta.json').is_file()
            assert (platform_dir / 'manual-publish.md').is_file()
            receipt = json.loads((platform_dir / '.creatoros-agent.json').read_text(encoding='utf-8'))
            assert receipt['manual_publish'] is True
            assert receipt['status'] == 'blocked'
            assert not list(platform_dir.glob('*.png'))
            assert not list(platform_dir.glob('*.mp4'))
            assert job['platform_outputs'][platform]['primary_text'].endswith(source)
            assert job['platform_outputs'][platform]['missing']
    finally:
        service.executor.shutdown()
