import { useEffect, useRef, useState } from 'react';
import { Empty, Message, PageHeader, errorText } from './components/shared';
import { listOfficialOutputs, officialOutputMediaUrl, readOfficialOutput, type OfficialOutputNode } from './api';

type PreviewState = {
  node: OfficialOutputNode;
  status: 'loading' | 'ready' | 'error';
  content: string;
  kind?: string;
  isBinary?: boolean;
  error?: string;
};

function Tree({ nodes, depth = 0, onOpen }: { nodes: OfficialOutputNode[]; depth?: number; onOpen: (node: OfficialOutputNode) => void }) {
  const indent = Math.min(depth * 16, 128);
  return <div className="output-tree">{nodes.map(node => <div className="output-node" key={node.path}>
    <div className="output-node-row" style={{ marginInlineStart: indent, maxWidth: `calc(100% - ${indent}px)` }}><span className={`output-icon ${node.type}`} aria-hidden="true">{node.type === 'dir' ? '▾' : '·'}</span><strong title={node.name}>{node.name}</strong><small>{node.type === 'dir' ? `${node.fileCount ?? node.children?.length ?? 0} 项` : `${node.kind ?? '文件'}${node.size ? ` · ${node.size} B` : ''}`}</small>{node.type === 'file' && <button type="button" className="link output-open-button" aria-label={`打开 ${node.name}`} onClick={() => onOpen(node)}>打开</button>}</div>{node.children?.length ? <Tree nodes={node.children} depth={depth + 1} onOpen={onOpen} /> : null}</div>)} </div>;
}

function formatPreview(node: OfficialOutputNode, content: string) {
  if (!/\.json$/i.test(node.name)) return content;
  try { return JSON.stringify(JSON.parse(content), null, 2); } catch { return content; }
}

export function OutputsPage() {
  const [nodes, setNodes] = useState<OfficialOutputNode[]>([]);
  const [error, setError] = useState('');
  const [preview, setPreview] = useState<PreviewState | null>(null);
  const requestId = useRef(0);
  const refresh = () => void listOfficialOutputs().then(setNodes).catch(e => setError(errorText(e)));
  const openOutput = async (node: OfficialOutputNode) => {
    const currentRequest = ++requestId.current;
    setPreview({ node, status: 'loading', content: '' });
    try {
      const result = await readOfficialOutput(node.path);
      if (currentRequest !== requestId.current) return;
      setPreview({ node, status: 'ready', content: result.isBinary ? '' : formatPreview(node, result.content), kind: result.kind, isBinary: result.isBinary });
    } catch (cause) {
      if (currentRequest !== requestId.current) return;
      setPreview({ node, status: 'error', content: '', error: errorText(cause) });
    }
  };
  const closePreview = () => { requestId.current += 1; setPreview(null); };
  const downloadText = () => {
    if (!preview || preview.status !== 'ready' || preview.isBinary) return;
    const blob = new Blob([preview.content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = preview.node.name;
    link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 0);
  };
  useEffect(refresh, []);
  return <>
    <PageHeader title="产物树" description="工作流产物按知序的运行目录展示，便于追踪来源、查看草稿和继续编辑。目录只读，发布仍需在发布中心显式操作。"><button type="button" className="secondary" onClick={refresh}>刷新</button></PageHeader>
    {error && <Message error>{error} <button type="button" className="link" onClick={refresh}>重试</button></Message>}
    <section className="panel outputs-panel">{nodes.length ? <Tree nodes={nodes} onOpen={openOutput} /> : <Empty title="还没有运行产物"><p>启动一次一键工作流后，素材核验、写作计划、平台改写和检查结果会按作业归档到这里。</p></Empty>}
      {preview && <section className="output-preview" aria-live="polite" aria-busy={preview.status === 'loading'}>
        <header className="output-preview-head"><div><span className="output-preview-kicker">产物预览</span><h2 title={preview.node.path}>{preview.node.name}</h2><small>{preview.node.path}</small></div><button type="button" className="quiet-button" onClick={closePreview} aria-label="关闭预览">关闭</button></header>
        {preview.status === 'loading' && <div className="output-preview-state">正在读取产物…</div>}
        {preview.status === 'error' && <Message error>{preview.error || '产物读取失败'} <button type="button" className="link" onClick={() => void openOutput(preview.node)}>重试</button></Message>}
        {preview.status === 'ready' && preview.isBinary && <div className="output-preview-state"><p>该文件为 {preview.kind || '二进制'} 文件，无法在文本预览中显示。</p><a className="secondary" href={officialOutputMediaUrl(preview.node.path)} download={preview.node.name}>下载 {preview.node.name}</a></div>}
        {preview.status === 'ready' && !preview.isBinary && <><pre className="output-preview-content">{preview.content || '（空文件）'}</pre><div className="output-preview-actions"><button type="button" className="secondary" onClick={downloadText}>下载文本</button><span>{preview.content.length.toLocaleString('zh-CN')} 字符</span></div></>}
      </section>}
    </section>
  </>;
}
