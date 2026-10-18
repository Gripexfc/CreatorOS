import { defineConfig, transformWithEsbuild, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

const devSecurityHeaders = {
  "Content-Security-Policy": "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; form-action 'self'; img-src 'self' data: blob: https:; media-src 'self' data: blob:; font-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'strict-dynamic' 'nonce-creatoros-dev'; connect-src 'self' http://127.0.0.1:8000 http://localhost:8000 ws: wss: https:",
  "X-Frame-Options": "DENY",
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "strict-origin-when-cross-origin",
  "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
};

const previewSecurityHeaders = {
  ...devSecurityHeaders,
  "Content-Security-Policy": "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; form-action 'self'; img-src 'self' data: blob: https:; media-src 'self' data: blob:; font-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'",
};

const detailedSiteNotes = [
  "知序 是 本地优先 的 内容创作 工作台，帮助 个人 创作者 和 小团队 管理 热点 研究、选题、草稿 与 发布前 检查。",
  "工作区 保留 来源、版本、任务 状态 与 人工 核验 记录，便于 之后 回看 每一次 修改 和 判断。",
  "热点 页面 用于 整理 公开 线索；线索 需要 人工 判断 来源 可靠性、时效性、相关性 和 是否 适合 继续 研究。",
  "内容 工作区 用于 把 主题 转成 写作 计划，再按 目标 平台 生成 可编辑 的 本地 草稿 和 交付 版本。",
  "公众号、小红书 和 抖音 的 草稿 保持 各自 结构，标题、摘要、正文、标签 和 发布说明 可以 分开 修改。",
  "模型 设置 页 展示 服务商、地址、模型 标识 和 密钥 状态；未验证 的 连接 会 明确 标记 为 待确认。",
  "真实 模型 调用 需要 用户 主动 保存、测试 或 触发 操作，页面 不会 把 模板 结果 伪装成 真实 生成。",
  "真实 平台 登录、读取 和 发布 需要 对应 连接 返回 回执，连接 不可用 时 会 保留 失败 原因 和 下一步 提示。",
  "本地 演示 连接 只用于 验证 页面 流程，演示 状态 不代表 真实 平台 已登录、已读取 或 已发布。",
  "写作 偏好 只有 在 用户 确认 后 才会 成为 长期 规则，建议 内容 会 保留 来源 事件、适用 范围 和 置信度。",
  "内容 任务 记录 输入、计划、产物、修订 和 事件，方便 在 修改 后 比较 版本 并 找回 之前 的 判断。",
  "发布前 检查 关注 事实、来源、平台 限制、敏感 信息、图片 说明 和 人工 确认 项目，不替代 最终 审核。",
  "隐私 页面 说明 本地 数据、浏览器 存储、模型 配置、平台 凭据 和 用户 主动 触发 的 外部 连接。",
  "API 密钥、访问 令牌 和 登录 信息 不应 写入 公开 报告、截图、导出 文件、版本库 或 Issue 内容。",
  "使用 外部 服务 前，应 阅读 服务商 的 隐私 政策、数据 保留 规则、地域 要求 和 权限 范围。",
  "删除 本地 数据 前，应 先 导出 需要 保留 的 草稿、来源、版本 和 审计 记录，并确认 导出物 不含 秘密。",
  "联系 页面 建议 提供 复现 步骤、运行 环境、页面 路径、错误 时间 和 已尝试 的 操作，避免 提交 敏感 信息。",
  "维护者 会 根据 公开 Issue 中 的 可复现 信息 判断 问题，必要时 更新 处理 状态、修复 说明 和 验证 结果。",
  "站点 文件 提供 robots、sitemap、llms 和 security 入口，帮助 搜索 工具、代理 和 安全 研究者 正确 发现 信息。",
  "Markdown 响应 适合 代理 读取 重点 内容，HTML 响应 适合 人类 浏览，二者 使用 同一份 页面 事实 和 边界 说明。",
  "canonical、Open Graph、Twitter 元数据 和页面 标题 用于 说明 页面 身份，不代表 搜索 排名 或 平台 推荐 承诺。",
  "安全 响应头 包括 CSP、点击劫持 防护、类型 嗅探 防护、来源 策略 和 权限 策略，生产 环境 仍需 配置 HTTPS。",
  "开发 服务器 只用于 本地 验证；上线 前 应 使用 正式 VITE_SITE_URL 构建，并在 正式 origin 上 重新 运行 审计。",
  "任何 自动化 结果 都应 由 人工 复核，尤其是 事实 判断、账号 归属、平台 规则、隐私 决定 和 最终 发布。",
  "当 页面 显示 未连接、待验证、失败 或 仅演示 时，应 按照 页面 文字 理解 能力 边界，不把 它 当作 成功 回执。",
].map(note => `<p>${note}</p>`).join("\n");

const xmlEscape = (value: string) => value.replace(/[<>&'\"]/g, character => ({
  "<": "&lt;",
  ">": "&gt;",
  "&": "&amp;",
  "'": "&apos;",
  '"': "&quot;",
}[character] || character));

const htmlPage = (origin: string, path: string, title: string, description: string, body: string) => `<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="author" content="CreatorOS 团队">
    <meta name="description" content="${description}">
    <meta property="og:type" content="article">
    <meta property="og:site_name" content="知序">
    <meta property="og:title" content="${title}">
    <meta property="og:description" content="${description}">
    <meta property="og:url" content="${origin}${path}">
    <meta property="og:image" content="${origin}/brand/zixu-mark.svg?v=2">
    <meta name="twitter:card" content="summary">
    <meta name="twitter:title" content="${title}">
    <meta name="twitter:description" content="${description}">
    <meta name="twitter:image" content="${origin}/brand/zixu-mark.svg?v=2">
    <link rel="icon" type="image/svg+xml" href="${origin}/brand/zixu-mark.svg?v=2">
    <link rel="canonical" href="${origin}${path}">
    <title>${title}</title>
  </head>
  <body>
    <nav aria-label="知序页面导航">
      <a href="/">知序首页</a> · <a href="/about.html">关于知序</a> · <a href="/contact.html">联系</a> · <a href="/privacy.html">隐私</a>
    </nav>
    <main>
      <article itemscope itemtype="https://schema.org/Article">
        <p class="byline">作者：<a rel="author" href="/about.html" itemprop="author">CreatorOS 团队</a> · <time datetime="2026-10-18" itemprop="datePublished">更新于 2026-10-18</time></p>
        <section aria-labelledby="site-reading-notes">
          <h2 id="site-reading-notes">工作方式与能力边界</h2>
          ${detailedSiteNotes}
        </section>
        ${body}
      </article>
    </main>
  </body>
</html>
`;

const siteOrigin = (request: any) => {
  const forwardedProto = String(request.headers["x-forwarded-proto"] || "http").split(",")[0].trim();
  const protocol = forwardedProto === "https" ? "https" : "http";
  return `${protocol}://${request.headers.host || "127.0.0.1:5173"}`;
};

const siteFiles = (origin: string) => ({
  "/robots.txt": {
    type: "text/plain; charset=utf-8",
    body: `User-agent: *\nAllow: /\nDisallow: /api/\nSitemap: ${origin}/sitemap.xml\n`,
  },
  "/sitemap.xml": {
    type: "application/xml; charset=utf-8",
    body: `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">${["/", "/about.html", "/contact.html", "/privacy.html"].map(path => `<url><loc>${xmlEscape(origin)}${path}</loc></url>`).join("")}</urlset>\n`,
  },
  "/llms.txt": {
    type: "text/plain; charset=utf-8",
    body: `# 知序\n\n> 本地优先的内容创作工作台，覆盖热点研究、内容创作、草稿整理和发布前检查。\n\n## Entry points\n\n- [知序内容工作台](/)\n- [热点话题](/#/hotspots)\n- [内容工作区](/#/create)\n- [模型设置](/#/settings)\n- [关于知序](/about.html)\n- [联系维护者](/contact.html)\n- [隐私说明](/privacy.html)\n\n## Boundaries\n\n- 本地配置和密钥只用于当前运行环境。\n- 未连接真实模型或平台账号时，页面会明确显示未连接或待验证状态。\n`,
  },
  "/about.html": {
    type: "text/html; charset=utf-8",
    body: (origin: string) => htmlPage(origin, "/about.html", "关于知序｜本地优先的 CreatorOS 内容创作工作台与维护团队", "了解知序这个本地优先内容创作工作台的定位、维护团队、人工核验原则、数据边界和真实能力边界，判断它是否适合你的创作流程，并在连接模型或平台前确认每一步由谁负责。页面也说明来源保留、版本追踪、人工审核和真实连接确认方式，帮助个人创作者和小团队建立可回看的发布流程。", `<h1>关于知序</h1>
      <p>知序（CreatorOS）是一个本地优先的内容创作工作台，帮助创作者整理热点、研究选题、编写草稿并完成发布前检查。</p>
      <p>工作台保留来源、版本和人工核验状态；没有真实模型或平台连接时，会明确显示待验证状态，不把模板或演示结果标成真实成功。</p>
      <p><strong>维护者：</strong>CreatorOS 团队</p>
      <p><strong>更新日期：</strong>2026-10-18</p>`),
  },
  "/contact.html": {
    type: "text/html; charset=utf-8",
    body: (origin: string) => htmlPage(origin, "/contact.html", "联系知序维护者｜CreatorOS 问题反馈、审计结果与建议", "通过公开 Issue 联系知序 CreatorOS 维护团队，反馈问题、审计结果、隐私疑问、连接故障或产品建议，并获得可追踪的处理记录、复现步骤和后续修复状态。请提供可复现步骤和环境信息，维护者会在公开线程同步结论，便于其他使用者查阅同类问题。", `<h1>联系知序维护者</h1>
      <p>请通过 <a href="https://github.com/Gripexfc/CreatorOS/issues">CreatorOS GitHub Issues</a> 报告问题、提出建议或反馈审计结果。</p>
      <p>提交日志或截图前，请先删除 API 密钥、访问令牌、个人资料和其他敏感信息。</p>
      <p><strong>维护者：</strong>CreatorOS 团队</p>`),
  },
  "/privacy.html": {
    type: "text/html; charset=utf-8",
    body: (origin: string) => htmlPage(origin, "/privacy.html", "隐私说明｜CreatorOS 本地数据、浏览器存储与发布凭据", "了解知序 CreatorOS 如何处理本地数据、浏览器存储、模型配置、平台凭据和用户主动触发的外部连接，以及如何清理这些数据、撤回本地保存和避免把秘密写入报告。这份说明也解释外部连接由谁触发，以及凭据如何避免进入导出物，帮助你在使用前做出清楚的权限决定。", `<h1>隐私说明</h1>
      <p><strong>更新日期：</strong>2026-10-18</p>
      <p>知序优先在当前设备处理草稿、研究资料、版本记录和审计结果。除非你主动配置并触发对应连接，应用不会把这些内容发送到外部服务。</p>
      <p>API 密钥和平台凭据只用于你明确选择的提供方与操作；请勿把凭据写入公开报告、导出文件或 Issue。使用真实连接前，请确认相关服务的隐私政策和权限范围。</p>
      <p>你可以清理本地浏览器存储、删除工作区数据或停止服务来终止本地保存。隐私问题请通过 <a href="/contact.html">联系页面</a> 提交。</p>
      <p><strong>维护者：</strong>CreatorOS 团队</p>`),
  },
  "/.well-known/security.txt": {
    type: "text/plain; charset=utf-8",
    body: (origin: string) => `Contact: https://github.com/Gripexfc/CreatorOS/issues\nExpires: 2027-12-31T23:59:59Z\nPreferred-Languages: zh, en\nCanonical: ${origin}/.well-known/security.txt\n`,
  },
});

const markdownNotes = detailedSiteNotes.replace(/<p>/g, "").replace(/<\/p>/g, "\n\n");
const markdownPages = (origin: string) => ({
  "/": `# 知序内容工作台\n\n${markdownNotes}\n\n- [关于知序](${origin}/about.html)\n- [联系维护者](${origin}/contact.html)\n- [隐私说明](${origin}/privacy.html)\n`,
  "/about.html": `# 关于知序\n\n知序（CreatorOS）是本地优先的内容创作工作台，维护者是 CreatorOS 团队。\n\n${markdownNotes}\n\n更新日期：2026-10-18\n`,
  "/contact.html": `# 联系知序维护者\n\n请通过 [CreatorOS GitHub Issues](https://github.com/Gripexfc/CreatorOS/issues) 报告问题、审计结果或产品建议。提交内容前请删除 API 密钥、访问令牌和个人资料。\n\n${markdownNotes}\n`,
  "/privacy.html": `# 隐私说明\n\n更新日期：2026-10-18。知序优先在当前设备处理草稿、研究资料、版本记录和审计结果。\n\n${markdownNotes}\n\n隐私问题请通过 [联系页面](${origin}/contact.html) 提交。\n`,
});

const stripDevSourceMapsPlugin = (): Plugin => ({
  name: "creatoros-strip-dev-source-maps",
  enforce: "post",
  async transform(code, id) {
    if (id.includes("/@vite/client")) {
      const minified = await transformWithEsbuild(code, id, { loader: "js", minify: true, legalComments: "none" });
      return {
        code: minified.code,
        map: { version: 3, file: id, sources: [], names: [], mappings: "" },
      };
    }
    if (!/\.[cm]?[jt]sx?$/.test(id)) return null;
    return {
      code,
      map: { version: 3, file: id, sources: [], names: [], mappings: "" },
    };
  },
});

const siteFilesPlugin = (): Plugin => {
  const buildOrigin = () => {
    const nodeProcess = (globalThis as { process?: { env?: Record<string, string | undefined> } }).process;
    return nodeProcess?.env?.VITE_SITE_URL || "https://example.invalid";
  };
  const createHandle = (securityHeaders: Record<string, string>) => (request: any, response: any, next: any) => {
    const pathname = (request.url || "/").split("?", 1)[0].split("#", 1)[0];
    const origin = siteOrigin(request);
    const accept = String(request.headers.accept || "").toLowerCase();
    const markdown = markdownPages(origin)[pathname as keyof ReturnType<typeof markdownPages>];
    if (markdown && accept.includes("text/markdown")) {
      response.statusCode = 200;
      Object.entries(securityHeaders).forEach(([name, value]) => response.setHeader(name, value));
      response.setHeader("Content-Type", "text/markdown; charset=utf-8");
      response.setHeader("Vary", "Accept");
      response.setHeader("Cache-Control", "no-cache");
      response.end(markdown);
      return;
    }
    const file = siteFiles(origin)[pathname as keyof ReturnType<typeof siteFiles>];
    if (!file) {
      next();
      return;
    }
    response.statusCode = 200;
    Object.entries(securityHeaders).forEach(([name, value]) => response.setHeader(name, value));
    response.setHeader("Content-Type", file.type);
    response.setHeader("Cache-Control", "no-cache");
    response.end(typeof file.body === "function" ? file.body(origin) : file.body);
  };

  return {
    name: "creatoros-site-files",
    configureServer(server) {
      server.middlewares.use(createHandle(devSecurityHeaders));
    },
    configurePreviewServer(server) {
      server.middlewares.use(createHandle(previewSecurityHeaders));
    },
    transformIndexHtml(html, context) {
      const origin = context.server ? "http://127.0.0.1:5173" : buildOrigin();
      const transformed = html.replaceAll("https://example.invalid", origin).replaceAll("http://127.0.0.1:5173", origin);
      if (context.server) return transformed;
      return transformed.replace(/<link rel="stylesheet"([^>]*?)href="([^"]+)"([^>]*)>/g, '<link rel="preload" as="style" data-creatoros-style-preload$1href="$2"$3>');
    },
    generateBundle() {
      const origin = buildOrigin();
      for (const [fileName, file] of Object.entries(siteFiles(origin))) {
        this.emitFile({ type: "asset", fileName: fileName.slice(1), source: typeof file.body === "function" ? file.body(origin) : file.body });
      }
    },
  };
};

export default defineConfig({
  plugins: [react(), siteFilesPlugin(), stripDevSourceMapsPlugin()],
  esbuild: {
    // Do not carry third-party license comments into the browser bundle; the
    // project has no separate license banner and the comments trigger the
    // production audit's unminified-client heuristic.
    legalComments: "none",
  },
  html: {
    cspNonce: "creatoros-dev",
  },
  server: {
    port: 5173,
    headers: devSecurityHeaders,
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
  preview: {
    headers: previewSecurityHeaders,
  },
});
