# 知序创作台

知序创作台是一个运行在本机的内容创作工作台。它把热点发现、写作画像、主题策划、平台改写、内容保存和账号复盘放在同一个本地应用里，适合个人创作者在自己的电脑上完成从选题到交付的完整过程。

仓库中的 Python 包名仍是 `creatoros`，前端目录是 `web/frontend`。产品默认使用中文界面，数据和运行日志保存在本机，不会自动上传到云端。

## 能做什么

默认侧栏只保留六个入口，其他页面通过工作流按钮进入：

| 页面 | 用途 |
| --- | --- |
| **画像** | 记录身份、领域、读者、内容支柱、语气、禁用词和平台偏好。每次保存都会生成一个版本，可以查看差异，也可以恢复旧版本形成新版本。 |
| **热点话题** | 读取抖音、微博、知乎公开热榜，支持搜索、刷新、查看来源、收藏线索，并把一个话题带入创作。数据失败时会明确显示不可用，不会用假数据填充。 |
| **内容工作区** | 从主题或素材开始，选择公众号、小红书或抖音，决定文章、配图、图文或脚本交付方式，执行研究、选题、主稿、平台适配、检查和保存流程。结果可以继续编辑、保存到内容库或下载。 |
| **模型设置** | 配置模型服务商、服务地址、访问密钥和模型编号，获取模型列表并执行最小测试。页面会显示本地模型网关是否已启动。 |
| **账号分析** | 导入公众号、小红书或抖音后台导出的 CSV/JSON，查看样本分布、平台表现、内容支柱和可解释的优化线索。没有真实数据时保持空白，不生成虚假的增长率。 |
| **拆解** | 粘贴文章、笔记、脚本或网页链接，按目标平台拆解标题、开头、结构、信息密度和互动触发，再生成属于自己的原创角度。不会逐句拼接原文。 |

工作流中还提供内容库、发布前检查、公众号草稿、输出文件、账号连接和对话助手等页面。它们都以“本地产物”和“真实平台回执”分开显示：生成完成不等于发布完成，保存草稿也不等于已经提交平台。

## 第一次使用

1. 启动前后端服务。
2. 打开“模型设置”，填写服务商、服务地址、访问密钥和模型编号，点击“保存并测试”。
3. 打开“画像”，填写自己的定位、读者和表达习惯并保存。
4. 进入“热点话题”选择一个线索，或直接进入“内容工作区”输入主题。
5. 选择目标平台和交付方式，补充自己的素材，开始生成。
6. 检查结果和待补材料，修改正文后保存到内容库或下载文件。
7. 后续在“账号分析”导入真实后台数据，再根据自己的样本复盘下一轮选题。

没有配置模型时，页面仍然可以打开、查看本地数据和使用热点/导入功能；需要调用模型的生成和拆解操作会明确提示先完成模型设置。

## macOS / Linux 启动

### 环境要求

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- Node.js 20 以上（包含 npm）

### 安装依赖

```bash
cd CreatorOS
make install
```

`make install` 会创建 `.venv312`、安装后端依赖，并在 `web/frontend` 安装前端依赖。首次安装也可以直接执行：

```bash
make install && make dev
```

### 一键启动

```bash
make dev
```

启动后访问：

- 前端：<http://127.0.0.1:5173/#/create>
- API 状态：<http://127.0.0.1:8000/api/v1/status>

`make dev` 会同时启动 API 和前端，并等待两个服务就绪。回到终端按 `Ctrl-C` 会同时停止它们。

前端端口被占用时，可以换一个端口：

```bash
make dev FRONTEND_PORT=5176
```

对应页面地址是 <http://127.0.0.1:5176/#/create>。

### 分开启动

只启动后端：

```bash
make backend
```

只启动前端：

```bash
make frontend
```

手动启动后端时，确保前端代理指向 `http://127.0.0.1:8000`。首次启动会自动执行数据库迁移；需要单独执行迁移时运行：

```bash
make db-upgrade
```

## Windows 安装与启动

### 安装要求

- Windows 10/11
- Node.js 24.16 以上，包含 npm
- Python 3.12，并勾选 **Add Python to PATH**
- 能访问 npm 和 Python 包下载地址的网络

Windows 安装脚本会自动创建 `.venv312`、安装后端和前端依赖，并安装本地模型网关 OpenClaw。模型网关用于把模型服务接入内容生成流程；不配置模型密钥时，前端仍能启动，但生成会停在模型配置提示处。

### 一键安装

将仓库放到本地后，在项目根目录双击：

```text
install-windows.bat
```

也可以在 PowerShell 中运行：

```powershell
cd C:\Users\你的用户名\Desktop\CreatorOS
.\install-windows.bat
```

### 一键启动前后端

安装完成后，在项目根目录双击：

```text
start-all-windows.bat
```

脚本会依次完成以下工作：

1. 准备 `runtime` 和模型工作目录。
2. 检查 8000 端口；没有服务时启动 API，已有健康 API 时复用它。
3. 等待数据库迁移和 API 就绪。
4. 检查 5173 端口；没有前端时启动 Vite，已有前端时复用它。
5. 检查模型网关状态；如果已经保存模型配置，会尝试启动本地模型服务。
6. 自动打开 <http://127.0.0.1:5173/#/create>。

停止服务时，关闭脚本打开的 API PowerShell 窗口和前端 CMD 窗口即可。代码更新后，先关闭旧窗口，再重新运行启动脚本；浏览器使用 `Ctrl+F5` 强制刷新。

### Windows 分开启动命令

PowerShell 中启动 API：

```powershell
cd C:\Users\你的用户名\Desktop\CreatorOS
.\.venv312\Scripts\python.exe -m creatoros web --host 127.0.0.1 --port 8000
```

PowerShell 中启动前端：

```powershell
cd C:\Users\你的用户名\Desktop\CreatorOS\web\frontend
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Git Bash 中启动 API：

```bash
cd /c/Users/你的用户名/Desktop/CreatorOS
./.venv312/Scripts/python.exe -m creatoros web --host 127.0.0.1 --port 8000
```

Git Bash 中启动前端：

```bash
cd /c/Users/你的用户名/Desktop/CreatorOS/web/frontend
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

在 `cmd.exe` 中，路径要使用 Windows 写法，不要写 `./`：

```bat
cd /d C:\Users\你的用户名\Desktop\CreatorOS
.venv312\Scripts\python.exe -m creatoros web --host 127.0.0.1 --port 8000
```

如果只需要重新安装模型网关，可以双击：

```text
install-openclaw-windows.bat
```

### Windows 每日热点

首次设置每天自动抓取热点：

```bat
setup-daily-trends-windows.bat
```

默认每天 08:00 执行。需要自定义时间时，例如每天 21:30：

```bat
setup-daily-trends-windows.bat 21:30
```

任务会优先刷新正在运行的 API；API 未启动时会独立抓取并写入 `data/trend-cache.json`。日志写入 `runtime/logs/`。手动抓取可以运行：

```powershell
.\.venv312\Scripts\python.exe -m creatoros fetch-trends --platforms douyin,weibo,zhihu --limit 12
```

## 常用命令

```bash
# 运行后端测试和前端测试
make test

# 编译 Python、检查前端类型
make lint

# 前端生产构建
cd web/frontend && npm run build

# 单独升级数据库
make db-upgrade

# 抓取公开热点并写入本地缓存
.venv312/bin/python -m creatoros fetch-trends --platforms douyin,weibo,zhihu --limit 12
```

Windows 使用 `.venv312\Scripts\python.exe`，macOS/Linux 使用 `.venv312/bin/python`。

## 配置与本地数据

默认配置不需要创建 `.env`。需要自定义时，通过进程环境变量传入：

| 变量 | 默认值 | 作用 |
| --- | --- | --- |
| `CREATOROS_DATA_DIR` | 项目根目录 `data/` | SQLite、素材、热点缓存和本地账号工作目录 |
| `CREATOROS_HOST` | `127.0.0.1` | API 监听地址 |
| `CREATOROS_PORT` | `8000` | API 端口 |
| `CREATOROS_FRONTEND_ORIGIN` | `http://127.0.0.1:5173` | 前端来源校验 |
| `CREATOROS_WECHAT_ADAPTER` | `mock` | 公众号连接方式；真实浏览器连接需额外安装依赖 |
| `CREATOROS_WECHAT_PROFILE_DIR` | `data/wechat-profile/` | 公众号浏览器会话目录 |

主要本地目录：

- `data/creatoros.sqlite3`：任务、画像、草稿、版本和导入记录。
- `data/assets/`：用户主动上传的素材和内容附件。
- `data/trend-cache.json`：公开热点缓存。
- `runtime/`：运行目录、模型工作区和日志。
- `web/frontend/dist/`：前端生产构建输出，开发启动不依赖它。

这些运行数据已加入 Git 忽略规则，不会随代码提交。备份或迁移时，请按需复制 `data/` 和 `runtime/`，不要提交访问密钥、Cookie、二维码或浏览器会话。

## 外部平台与模型边界

- 热点数据来自公开榜单，只是选题线索；原始来源、抓取时间和失败状态会保留。
- 账号分析只分析你导入的真实数据，不会自动猜测行业基准。
- 生成内容需要可用的模型服务和访问密钥；本地模板或演示状态不会标成真实模型结果。
- 登录、读取账号、提交草稿和发布都需要用户明确操作；知序不会代填密码，也不会自动群发。
- 保存到内容库表示可以继续编辑、回看和下载，不代表已经审核通过或发布成功。

## 常见问题

### 页面提示 `ECONNREFUSED 127.0.0.1:8000`

API 没有启动，或浏览器连接到了已经退出的旧进程。关闭占用 8000 的旧终端，再运行 `start-all-windows.bat`；也可以先用上面的手动 API 命令确认后端日志。

### Windows 提示端口已被占用

PowerShell 查看占用进程：

```powershell
Get-NetTCPConnection -LocalPort 8000,5173 -ErrorAction SilentlyContinue | Select-Object LocalPort,OwningProcess
```

结束进程：

```powershell
Stop-Process -Id 进程号 -Force
```

确认没有旧窗口后，再重新启动。

### Windows 提示无法创建目录联接或 `WinError 1314`

优先使用 `start-all-windows.bat`，不要直接导入内部模块。若仍提示权限不足，在 Windows 设置中打开“开发者模式”，或用管理员身份运行一次启动脚本。

### 模型设置已保存但仍不能生成

先确认服务地址、访问密钥和模型编号正确，再点击“保存并测试”。Windows 用户还要确认 OpenClaw 已安装，启动脚本日志显示模型网关已启动；修改配置后请重启 API。

### 热点显示“暂时无法获取”

这是外部榜单或网络请求失败的真实状态。先点击页面刷新；如果仍失败，查看 `runtime/logs/`，或手动执行 `fetch-trends` 检查网络和证书环境。已有缓存会在可用时继续被页面读取。

### 浏览器看不到刚更新的 Logo 或样式

停止旧前端后重新运行启动脚本，并在页面按 `Ctrl+F5`。如果 5173 仍复用旧 Vite 进程，先结束该进程再启动。

## 开发检查

提交前建议运行：

```bash
git diff --check
make test
make lint
cd web/frontend && npm run build
```

后端接口文档在 API 启动后可通过 <http://127.0.0.1:8000/docs> 查看。
