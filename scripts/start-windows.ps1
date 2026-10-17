$ErrorActionPreference = 'Stop'

$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $root '.venv312\Scripts\python.exe'
$frontend = Join-Path $root 'web\frontend'
$vite = Join-Path $frontend 'node_modules\vite\bin\vite.js'
$apiUrl = 'http://127.0.0.1:8000/api/v1/status'
$frontendUrl = 'http://127.0.0.1:5173'

if (-not (Test-Path $python)) {
    Write-Host "尚未安装后端依赖，请先双击 install-windows.bat。" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $vite)) {
    Write-Host "尚未安装前端依赖，请先双击 install-windows.bat。" -ForegroundColor Red
    exit 1
}

function Wait-ForUrl {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [int]$TimeoutSeconds = 60
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 2
            if ($response.StatusCode -eq 200) {
                return $true
            }
        }
        catch {
            Start-Sleep -Milliseconds 500
        }
    } while ((Get-Date) -lt $deadline)
    return $false
}

$escapedRoot = $root.Replace("'", "''")
$escapedPython = $python.Replace("'", "''")
$apiCommand = "Set-Location -LiteralPath '$escapedRoot'; & '$escapedPython' -m uvicorn creatoros.api.app:app --host 127.0.0.1 --port 8000"
$env:VITE_API_BASE_URL = 'http://127.0.0.1:8000'
$env:CREATOROS_FRONTEND_ORIGIN = $frontendUrl

Write-Host "正在启动 API（8000）…" -ForegroundColor Cyan
Start-Process -FilePath 'powershell.exe' -WorkingDirectory $root -ArgumentList @(
    '-NoExit',
    '-NoProfile',
    '-ExecutionPolicy',
    'Bypass',
    '-Command',
    $apiCommand
)

Write-Host "正在启动前端（5173）…" -ForegroundColor Cyan
Start-Process -FilePath 'cmd.exe' -WorkingDirectory $frontend -ArgumentList @(
    '/k',
    'npm run dev -- --host 127.0.0.1 --port 5173 --strictPort'
)

Write-Host "等待服务就绪…" -ForegroundColor Yellow
$apiReady = Wait-ForUrl -Url $apiUrl
$frontendReady = Wait-ForUrl -Url $frontendUrl
if (-not $apiReady -or -not $frontendReady) {
    Write-Host "服务未能在 60 秒内全部就绪，请查看新打开的两个终端窗口。" -ForegroundColor Red
    exit 1
}

Write-Host "前后端已启动，正在打开页面。" -ForegroundColor Green
Start-Process 'http://127.0.0.1:5173/#/create'
