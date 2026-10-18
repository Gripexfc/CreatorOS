$ErrorActionPreference = 'Stop'

$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $root '.venv312\Scripts\python.exe'
$frontend = Join-Path $root 'web\frontend'
$vite = Join-Path $frontend 'node_modules\vite\bin\vite.js'
$apiBaseUrl = 'http://127.0.0.1:8000'
$apiUrl = 'http://127.0.0.1:8000/api/v1/status'
$frontendUrl = 'http://127.0.0.1:5173'
$runtime = Join-Path $root 'runtime'
$workspace = Join-Path $runtime 'openclaw\workspace'
$runtimeOutputs = Join-Path $runtime 'outputs'
$skillSourceRoot = Join-Path $root 'vendor\easel\skills\openclaw'
$sharedSource = Join-Path $root 'vendor\easel\skills\shared'

if (-not (Test-Path $python)) {
    Write-Host "尚未安装后端依赖，请先双击 install-windows.bat。" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $vite)) {
    Write-Host "尚未安装前端依赖，请先双击 install-windows.bat。" -ForegroundColor Red
    exit 1
}

function Ensure-Junction {
    param(
        [Parameter(Mandatory = $true)][string]$Target,
        [Parameter(Mandatory = $true)][string]$Source
    )

    if (-not (Test-Path -LiteralPath $Source -PathType Container)) {
        throw "运行目录源不存在：$Source"
    }
    $parent = Split-Path -Parent $Target
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    if (Test-Path -LiteralPath $Target) {
        return
    }
    try {
        New-Item -ItemType Junction -Path $Target -Target $Source | Out-Null
    }
    catch {
        throw "无法创建 Windows 目录联接：$Target -> $Source。请启用开发者模式或以管理员身份运行。$($_.Exception.Message)"
    }
}

Write-Host "正在准备 Windows 运行目录…" -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path $runtimeOutputs, $workspace | Out-Null
Ensure-Junction -Target (Join-Path $workspace 'outputs') -Source $runtimeOutputs
Ensure-Junction -Target (Join-Path $workspace 'shared') -Source $sharedSource
$skillsTargetRoot = Join-Path $workspace 'skills'
New-Item -ItemType Directory -Force -Path $skillsTargetRoot | Out-Null
if (Test-Path -LiteralPath $skillSourceRoot -PathType Container) {
    Get-ChildItem -LiteralPath $skillSourceRoot -Directory | ForEach-Object {
        Ensure-Junction -Target (Join-Path $skillsTargetRoot $_.Name) -Source $_.FullName
    }
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

function Test-PortInUse {
    param([Parameter(Mandatory = $true)][int]$Port)

    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $client.Connect('127.0.0.1', $Port)
        return $true
    }
    catch {
        return $false
    }
    finally {
        $client.Dispose()
    }
}

$escapedRoot = $root.Replace("'", "''")
$escapedPython = $python.Replace("'", "''")
$apiCommand = "Set-Location -LiteralPath '$escapedRoot'; & '$escapedPython' -m creatoros web --host 127.0.0.1 --port 8000"
$env:VITE_API_BASE_URL = 'http://127.0.0.1:8000'
$env:CREATOROS_FRONTEND_ORIGIN = $frontendUrl
$env:CREATOROS_CURL_NO_REVOKE = '1'

Write-Host "检查 API（8000）…" -ForegroundColor Cyan
$apiReady = $false
if (Test-PortInUse -Port 8000) {
    Write-Host "检测到 8000 已占用，正在检查现有 API…" -ForegroundColor Yellow
    $apiReady = Wait-ForUrl -Url $apiUrl -TimeoutSeconds 10
    if ($apiReady) {
        Write-Host "复用已运行的 API。" -ForegroundColor Green
    }
    else {
        throw "端口 8000 已被占用，但现有服务没有返回 CreatorOS API。请关闭占用 8000 的进程后重试。"
    }
}
else {
    Write-Host "正在启动 API（8000）…" -ForegroundColor Cyan
    Start-Process -FilePath 'powershell.exe' -WorkingDirectory $root -ArgumentList @(
        '-NoExit',
        '-NoProfile',
        '-ExecutionPolicy',
        'Bypass',
        '-Command',
        $apiCommand
    )

    Write-Host "等待 API 完成数据库迁移并就绪…" -ForegroundColor Yellow
    $apiReady = Wait-ForUrl -Url $apiUrl -TimeoutSeconds 90
    if (-not $apiReady) {
        throw "API 在 90 秒内没有就绪，请查看 API PowerShell 窗口是否卡在数据库迁移或仍有错误。"
    }
}

# A healthy HTTP response can still come from an older CreatorOS process left
# on port 8000. Require the current model-status route before reusing it, so a
# code update never silently keeps the old backend alive.
try {
    $null = Invoke-RestMethod -UseBasicParsing -Uri "$apiBaseUrl/api/settings/models/status" -Method Get
}
catch {
    throw "端口 8000 上运行的不是当前 CreatorOS 后端。请关闭旧的 API PowerShell 窗口后，再重新运行 start-all-windows.bat。"
}

Write-Host "检查前端（5173）…" -ForegroundColor Cyan
$frontendReady = $false
if (Test-PortInUse -Port 5173) {
    Write-Host "检测到 5173 已占用，正在检查现有前端…" -ForegroundColor Yellow
    $frontendReady = Wait-ForUrl -Url $frontendUrl -TimeoutSeconds 10
    if ($frontendReady) {
        Write-Host "复用已运行的前端。" -ForegroundColor Green
    }
    else {
        throw "端口 5173 已被占用，但现有服务没有返回前端页面。请关闭占用 5173 的进程后重试。"
    }
}
else {
    Write-Host "API 已就绪，正在启动前端（5173）…" -ForegroundColor Cyan
    Start-Process -FilePath 'cmd.exe' -WorkingDirectory $frontend -ArgumentList @(
        '/k',
        'npm run dev -- --host 127.0.0.1 --port 5173 --strictPort'
    )

    Write-Host "等待前端就绪…" -ForegroundColor Yellow
    $frontendReady = Wait-ForUrl -Url $frontendUrl -TimeoutSeconds 60
    if (-not $frontendReady) {
        throw "前端在 60 秒内没有就绪，请查看前端 CMD 窗口。"
    }
}

if (-not $apiReady -or -not $frontendReady) {
    Write-Host "服务未能就绪，请查看新打开的终端窗口。" -ForegroundColor Red
    exit 1
}

Write-Host "检查本地模型服务…" -ForegroundColor Cyan
try {
    $modelStatus = Invoke-RestMethod -UseBasicParsing -Uri "$apiBaseUrl/api/settings/models/status" -Method Get
    if ($modelStatus.configExists -and $modelStatus.configured) {
        $modelStart = Invoke-RestMethod -UseBasicParsing -Uri "$apiBaseUrl/api/settings/models/start" -Method Post -ContentType 'application/json' -Body '{}'
        if ($modelStart.gatewayOnline) {
            Write-Host "模型网关已启动。" -ForegroundColor Green
        }
        else {
            Write-Host "模型网关尚未启动：$($modelStart.note)" -ForegroundColor Yellow
        }
    }
    else {
        Write-Host "尚未配置模型；启动后请到“模型设置”保存并测试。" -ForegroundColor Yellow
    }
}
catch {
    Write-Host "模型服务检查失败：$($_.Exception.Message)；前后端仍已启动。" -ForegroundColor Yellow
}

Write-Host "前后端已启动，正在打开页面。" -ForegroundColor Green
Start-Process 'http://127.0.0.1:5173/#/create'
