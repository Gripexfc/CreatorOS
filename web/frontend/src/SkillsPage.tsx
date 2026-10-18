import { useEffect, useMemo, useState } from 'react';
import { Empty, Message, PageHeader, errorText } from './components/shared';
import { listOfficialSkills, type OfficialSkill } from './api';

const skillLabels: Record<string, string> = {
  'xhs-note-creator': '小红书笔记创作',
  'skill-wechat-publisher': '公众号文章创作',
  'auto-short-video': '短视频脚本制作',
  'social-content': '平台内容写作',
  'copywriting': '文案写作',
  'card-design': '卡片设计',
  'skill-competitor-analysis': '参考内容拆解',
};
const layerLabels: Record<string, string> = { CREATOROS: '知序能力', OFFICIAL: '平台能力', LOCAL: '本地能力' };

export function SkillsPage() {
  const [skills, setSkills] = useState<OfficialSkill[]>([]);
  const [query, setQuery] = useState('');
  const [error, setError] = useState('');
  const refresh = () => void listOfficialSkills().then(setSkills).catch(e => setError(errorText(e)));
  useEffect(refresh, []);
  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return needle ? skills.filter(skill => `${skill.name} ${skill.description} ${skill.layer}`.toLowerCase().includes(needle)) : skills;
  }, [query, skills]);
  return <>
    <PageHeader title="技能库" description="把可复用的创作能力接入知序页面。每个技能保留来源层级和配置状态，未配置时只显示能力边界。">
      <label className="inline-search"><span className="sr-only">搜索技能</span><input value={query} onChange={e => setQuery(e.target.value)} placeholder="搜索技能" /></label>
      <button type="button" className="secondary" onClick={refresh}>刷新</button>
    </PageHeader>
    {error && <Message error>{error} <button type="button" className="link" onClick={refresh}>重试</button></Message>}
    {visible.length ? <section className="skill-grid">{visible.map(skill => <article className="skill-card" key={`${skill.layer}:${skill.name}`}>
      <div className="skill-card-head"><span className="kicker">{layerLabels[skill.layer] || '创作能力'}</span><span className={`state ${skill.apiConfigured ? 'success' : skill.needsApi ? 'warning' : ''}`}>{skill.apiConfigured ? '已配置' : skill.needsApi ? '需配置' : '本地可用'}</span></div>
      <h2>{skillLabels[skill.name] || '平台创作能力'}</h2><p>{skill.description || '暂无说明。'}</p>
      <small>{skill.needsApi ? '执行前会检查外部 API，不会生成伪造结果。' : '可在本地流程中直接调用。'}</small>
    </article>)}</section> : <Empty title={skills.length ? '没有匹配的技能' : '技能尚未读取'}><p>{skills.length ? '换一个关键词继续查找。' : '本地服务在线后会读取隔离的技能目录。'}</p></Empty>}
  </>;
}
