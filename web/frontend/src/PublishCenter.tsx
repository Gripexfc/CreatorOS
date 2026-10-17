import { useEffect, useMemo, useState } from 'react';
import { apiUrl, createWechatDraftFromArtifact, getContentTask, listConnectors, listContentTasks, listWorkflows, type Artifact, type ConnectorState, type ContentTask, type ContentTaskDetail, type WorkflowJob, type WorkflowPlatformOutput } from './api';
import { connectorStateName, dateLabel, Empty, errorText, Message, PageHeader, stateName } from './components/shared';

type Navigate = (path: string) => void;
const platformName = (platform: string) => platform === 'wechat' ? '公众号' : platform === 'xiaohongshu' ? '小红书' : '抖音';
const platformClass = (platform: string) => platform === 'wechat' ? 'wechat' : platform === 'xiaohongshu' ? 'xhs' : 'douyin';
const artifactTitle = (artifact: Artifact) => {
  const content = artifact.current_revision?.content ?? {};
  const candidates = Array.isArray(content.title_candidates) ? content.title_candidates : [];
  return String(content.title ?? candidates[0] ?? '未命名版本');
};
const workflowTitle = (job: WorkflowJob) => String(job.topic || '').split('\n')[0].trim() || `工作流 ${job.id.slice(0, 8)}`;
const workflowStatus = (status: WorkflowJob['status']) => ({ queued: '排队中', running: '生成中', completed: '已完成', blocked: '待补齐', failed: '失败', interrupted: '已停止' }[status]);
const platformKey = (platform: 'wechat' | 'xiaohongshu' | 'douyin') => platform === 'wechat' ? 'wechat-oa' : platform;
const outputStatus = (status?: string) => ({ completed: '已生成', ready: '已生成', draft: '草稿', blocked: '待补齐', failed: '失败', pending: '待生成' }[status || ''] || status || '待生成');
const workflowMediaUrl = (path: string) => apiUrl(`/api/media/${path.split('/').map(encodeURIComponent).join('/')}`);
const workflowReason = (job: WorkflowJob, output?: WorkflowPlatformOutput) => {
  const missing = output?.missing?.filter(Boolean) || [];
  if (missing.length) return missing.join('；');
  if (job.stages.adaptation?.reason) return job.stages.adaptation.reason;
  if (job.status !== 'completed') return job.stages[job.current || 'discovery']?.reason || `工作流${workflowStatus(job.status)}，可从未完成阶段重试`;
  return '平台版本尚未生成。';
};

function WorkflowPublishDetail({ job, connectors }: { job: WorkflowJob; connectors: ConnectorState[] }) {
  const connectorByPlatform = useMemo(() => new Map(connectors.map(item => [item.platform, item])), [connectors]);
  const outputs = job.platform_outputs || {};
  const platforms = ['wechat', 'xiaohongshu', 'douyin'] as const;
  return <>
    <div className="panel-title"><div><span className="kicker">发布前检查 · 真实工作流</span><h2>{workflowTitle(job)}</h2></div><span className="status-pill">{workflowStatus(job.status)}</span></div>
    <div className="publish-checks"><span className={`check ${job.status === 'completed' ? 'ok' : ''}`}>工作流 {workflowStatus(job.status)}</span><span className={`check ${Object.keys(outputs).length === 3 ? 'ok' : ''}`}>平台版本 {Object.keys(outputs).length}/3</span><span className="check">发布：手动确认，未调用平台发布接口</span></div>
    <p className="publish-truth-note">这里检查的是本地产物。登录、账号读取和真实发布仍需要你在平台完成，本页不会把生成成功写成发布成功。</p>
    <div className="publish-platform-grid">{platforms.map(platform => {
      const output = outputs[platformKey(platform)];
      const connector = connectorByPlatform.get(platform);
      const artifacts = output?.artifacts || [];
      return <article className={`publish-platform-card ${platformClass(platform)}`} key={platform}>
        <div className="publish-platform-head"><div><span className="kicker">{platformName(platform)}</span><h3>{output ? outputStatus(output.status) : '尚未生成'}</h3></div><span className="status-pill">{output ? outputStatus(output.status) : '待生成'}</span></div>
        <p>{output?.media_kind === 'script' ? '脚本，不含视频文件' : output?.media_kind === 'video' ? '视频文件' : output?.media_kind === 'image' ? '图文卡片' : output ? '平台内容包' : workflowReason(job, output)}</p>
        {output?.primary_text && <p><strong>主稿：</strong>{output.primary_text.split('/').pop()}</p>}
        {output?.copy_text && <details><summary>查看可复制发布文案</summary><pre>{output.copy_text}</pre></details>}
        {output?.missing?.length ? <ul>{output.missing.map((item, index) => <li key={`${item}-${index}`}>待补齐：{item}</li>)}</ul> : !output && <p className="muted">待补齐：{workflowReason(job, output)}</p>}
        {artifacts.length ? <ul>{artifacts.map(path => <li key={path}><a href={workflowMediaUrl(path)} target="_blank" rel="noopener noreferrer">{path.split('/').pop()}</a>{' '}<a href={workflowMediaUrl(path)} download>下载</a></li>)}</ul> : <p className="muted">暂无可下载文件</p>}
        {output?.checks?.length ? <details><summary>查看产物检查（{output.checks.length}）</summary><ul>{output.checks.map((check, index) => <li key={index}>{typeof check === 'string' ? check : JSON.stringify(check)}</li>)}</ul></details> : null}
        <div className="publish-platform-foot"><small>账号：{connector ? connectorStateName(connector.state) : '未读取'}</small><small>交付：下载后手动发布</small></div>
      </article>;
    })}</div>
  </>;
}

/** Easel 发布中心的本地版本：集中查看三平台版本，再明确进入真实账号动作。 */
export function PublishCenterPage({ initialTaskId, navigate }: { initialTaskId?: string; navigate: Navigate }) {
  const [tasks, setTasks] = useState<ContentTask[]>([]);
  const [workflows, setWorkflows] = useState<WorkflowJob[]>([]);
  const [detail, setDetail] = useState<ContentTaskDetail | null>(null);
  const [workflowDetail, setWorkflowDetail] = useState<WorkflowJob | null>(null);
  const [connectors, setConnectors] = useState<ConnectorState[]>([]);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const refresh = async (taskId?: string) => {
    // Keep the DB ContentTask chain usable when an older backend has not yet
    // exposed the Easel listing endpoint.
    const [next, nextWorkflows] = await Promise.all([listContentTasks(), listWorkflows().catch(() => [] as WorkflowJob[])]);
    setError('');
    setTasks(next); setWorkflows(nextWorkflows);
    const target = taskId || workflowDetail?.id || detail?.task.id || next[0]?.id;
    const workflow = nextWorkflows.find(item => item.id === target);
    if (workflow) { setWorkflowDetail(workflow); setDetail(null); }
    else if (target) { setDetail(await getContentTask(target)); setWorkflowDetail(null); }
    else { setDetail(null); setWorkflowDetail(null); }
  };
  useEffect(() => {
    void Promise.all([refresh(initialTaskId), listConnectors().then(setConnectors)]).catch(e => setError(errorText(e)));
  }, [initialTaskId]);

  const connectorByPlatform = useMemo(() => new Map(connectors.map(item => [item.platform, item])), [connectors]);
  // A quick-draft task and its Easel workflow can share the same title. Keep
  // the workflow row as the source of truth so the project list does not show
  // two entries for one generation run.
  const visibleTasks = useMemo(() => {
    const workflowTitles = new Set(workflows.map(workflowTitle));
    return tasks.filter(task => !workflowTitles.has(task.title.trim()));
  }, [tasks, workflows]);
  const visibleWorkflows = useMemo(() => {
    const latest = new Map<string, WorkflowJob>();
    for (const job of workflows) {
      const key = workflowTitle(job);
      const previous = latest.get(key);
      const stamp = Number(job.updated || job.created || 0);
      const previousStamp = Number(previous?.updated || previous?.created || 0);
      if (!previous || stamp >= previousStamp) latest.set(key, job);
    }
    return Array.from(latest.values());
  }, [workflows]);
  const action = async (artifact: Artifact) => {
    if (!artifact.current_revision_id) return;
    setBusy(true); setError(''); setNotice('');
    try {
      if (artifact.platform === 'wechat') {
        const draft = await createWechatDraftFromArtifact(artifact.id, artifact.current_revision_id);
        navigate(`drafts/${draft.id}`);
        setNotice(`已转入本地公众号草稿 ${draft.id.slice(0, 8)}，未调用微信发布接口。`);
      } else {
        const connector = connectorByPlatform.get(artifact.platform);
        setNotice(connector?.state === 'read_succeeded' || connector?.state === 'submit_succeeded'
          ? `${platformName(artifact.platform)}已具备本地连接状态，请人工确认后提交。`
          : `${platformName(artifact.platform)}尚未连接；先去账号完成连接和读取。`);
      }
    } catch (e) { setError(errorText(e)); }
    finally { setBusy(false); }
  };

  return <>
    <PageHeader title="发布中心" description="把已确认的版本交付到公众号、小红书和抖音。这里保留每个平台的独立状态，真实发布始终需要账号连接和你的确认。">
      <button className="secondary" onClick={() => void refresh()}>刷新版本</button>
    </PageHeader>
    {notice && <Message>{notice}</Message>}
    {error && <Message error>{error}</Message>}
    <div className="publish-layout">
      <section className="panel publish-projects">
        <div className="section-title"><div><span className="kicker">内容项目</span><h2>{visibleTasks.length + visibleWorkflows.length ? `${visibleTasks.length + visibleWorkflows.length} 个项目` : '还没有项目'}</h2></div><button className="primary" onClick={() => navigate('workspace')}>新建内容</button></div>
        {visibleTasks.length ? <><span className="kicker">内容库任务</span>{visibleTasks.map(task => <button className={`task-line ${detail?.task.id === task.id && !workflowDetail ? 'selected' : ''}`} key={task.id} onClick={() => void getContentTask(task.id).then(next => { setDetail(next); setWorkflowDetail(null); }).catch(e => setError(errorText(e)))}><span><strong>{task.title}</strong><small>{stateName(task.status)} · {dateLabel(task.updated_at)}</small></span><b>→</b></button>)}</> : null}
        {visibleWorkflows.length ? <><span className="kicker publish-project-group">Easel 工作流</span>{visibleWorkflows.slice(0, 20).map(job => <button className={`task-line ${workflowDetail?.id === job.id ? 'selected' : ''}`} key={job.id} onClick={() => { setWorkflowDetail(job); setDetail(null); }}><span><strong>{workflowTitle(job)}</strong><small>{workflowStatus(job.status)} · {Object.keys(job.platform_outputs || {}).length}/3 平台版本</small></span><b>→</b></button>)}</> : null}
        {!visibleTasks.length && !visibleWorkflows.length && <Empty title="还没有可发布内容">先从一键工作流生成主题，完成后平台版本会出现在这里。</Empty>}
      </section>
      <section className="panel publish-detail">
        {workflowDetail ? <WorkflowPublishDetail job={workflowDetail} connectors={connectors} /> : detail ? <>
          <div className="panel-title"><div><span className="kicker">发布前检查</span><h2>{detail.task.title}</h2></div><button className="secondary" onClick={() => navigate(`workspace/${detail.task.id}`)}>打开编辑</button></div>
          <div className="publish-checks"><span className={detail.latest_brief?.confirmation_status === 'confirmed' ? 'check ok' : 'check'}>写作计划 {detail.latest_brief?.confirmation_status === 'confirmed' ? '已确认' : '待确认'}</span><span className={detail.artifacts.length === 3 ? 'check ok' : 'check'}>三平台版本 {detail.artifacts.length}/3</span><span className="check">AI/素材：本地模板</span></div>
          {detail.artifacts.length === 0 ? <Empty title="还没有平台版本">回到工作流确认写作计划后，创建公众号、小红书、抖音三份独立版本。</Empty> : <div className="publish-platform-grid">{(['wechat', 'xiaohongshu', 'douyin'] as const).map(platform => {
            const artifact = detail.artifacts.find(item => item.platform === platform);
            const connector = connectorByPlatform.get(platform);
            return <article className={`publish-platform-card ${platformClass(platform)}`} key={platform}>
              <div className="publish-platform-head"><div><span className="kicker">{platformName(platform)}</span><h3>{artifact ? artifactTitle(artifact) : '尚未生成'}</h3></div><span className="status-pill">{artifact ? stateName(artifact.status) : '待生成'}</span></div>
              <p>{artifact ? `版本 ${artifact.current_revision?.revision_no ?? 0} · ${artifact.current_revision?.generation_kind === 'user_edit' ? '已编辑' : '本地模板'}` : '完成写作计划后生成'}</p>
              <div className="publish-platform-foot"><small>{connector ? `账号：${connectorStateName(connector.state)}` : '账号：未读取'}</small>{artifact && <button className="secondary" disabled={busy || !artifact.current_revision_id} onClick={() => void action(artifact)}>{platform === 'wechat' ? '转为公众号草稿' : '检查发布条件'}</button>}</div>
            </article>;
          })}</div>}
        </> : <Empty title="选择一个内容项目">查看平台独立版本、真实产物、检查结果和缺失原因。</Empty>}
      </section>
    </div>
  </>;
}
