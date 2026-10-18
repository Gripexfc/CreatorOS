$ErrorActionPreference = 'Stop'

$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $root '.venv312\Scripts\python.exe'
$dataDir = Join-Path $root 'data'
$logDir = Join-Path $root 'runtime\logs'
$apiUrl = 'http://127.0.0.1:8000/api/v1/trends?platforms=douyin,weibo,zhihu&limit=12&refresh=true'
$logPath = Join-Path $logDir ("daily-trends-{0}.log" -f (Get-Date -Format 'yyyyMMdd'))
$env:CREATOROS_CURL_NO_REVOKE = '1'

New-Item -ItemType Directory -Force -Path $logDir | Out-Null
if (-not (Test-Path -LiteralPath $python)) {
    throw "找不到项目 Python 环境：$python。请先运行 install-windows.bat。"
}

"[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] CreatorOS 每日热点抓取" | Tee-Object -FilePath $logPath

# API 已运行时直接刷新它的内存和磁盘缓存；未运行时使用 CLI 独立抓取。
try {
    $response = Invoke-WebRequest -UseBasicParsing -Uri $apiUrl -TimeoutSec 30
    if ($response.StatusCode -eq 200) {
        $response.Content | Tee-Object -FilePath $logPath -Append
        Write-Host "已通过运行中的 CreatorOS API 更新热点缓存。" -ForegroundColor Green
        exit 0
    }
}
catch {
    "API 未运行或暂时不可用，改用独立抓取：$($_.Exception.Message)" | Tee-Object -FilePath $logPath -Append
}

Push-Location $root
try {
    & $python -m creatoros fetch-trends --platforms douyin,weibo,zhihu --limit 12 2>&1 |
        Tee-Object -FilePath $logPath -Append
    $exitCode = $LASTEXITCODE
}
finally {
    Pop-Location
}

if ($exitCode -eq 0) {
    Write-Host "已完成每日热点抓取，缓存位置：$dataDir\trend-cache.json" -ForegroundColor Green
}
exit $exitCode
