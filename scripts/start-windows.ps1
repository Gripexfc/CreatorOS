$ErrorActionPreference = 'Stop'

$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $root '.venv312\Scripts\python.exe'
$frontend = Join-Path $root 'web\frontend'
$vite = Join-Path $frontend 'node_modules\vite\bin\vite.js'
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

foreach ($port in @(8000, 5173)) {
    if (Test-PortInUse -Port $port) {
        throw "端口 $port 已被占用。请先关闭旧的 CreatorOS API/Vite 窗口，再重新启动。"
    }
}

$escapedRoot = $root.Replace("'", "''")
$escapedPython = $python.Replace("'", "''")
$apiCommand = "Set-Location -LiteralPath '$escapedRoot'; & '$escapedPython' -m creatoros web --host 127.0.0.1 --port 8000"
$env:VITE_API_BASE_URL = 'http://127.0.0.1:8000'
$env:CREATOROS_FRONTEND_ORIGIN = $frontendUrl

Write-Host "正在启动 API（8000）…" -ForegroundColor Cyan
$apiProcess = Start-Process -FilePath 'powershell.exe' -WorkingDirectory $root -PassThru -ArgumentList @(
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
    if ($apiProcess.HasExited) {
        throw "API 启动失败（退出码 $($apiProcess.ExitCode)），请查看 API PowerShell 窗口。"
    }
    throw "API 在 90 秒内没有就绪，请查看 API PowerShell 窗口是否卡在数据库迁移或仍有错误。"
}

Write-Host "API 已就绪，正在启动前端（5173）…" -ForegroundColor Cyan
$frontendProcess = Start-Process -FilePath 'cmd.exe' -WorkingDirectory $frontend -PassThru -ArgumentList @(
    '/k',
    'npm run dev -- --host 127.0.0.1 --port 5173 --strictPort'
)

Write-Host "等待前端就绪…" -ForegroundColor Yellow
$frontendReady = Wait-ForUrl -Url $frontendUrl -TimeoutSeconds 60
if (-not $frontendReady) {
    if ($frontendProcess.HasExited) {
        throw "前端启动失败（退出码 $($frontendProcess.ExitCode)），请查看前端 CMD 窗口。"
    }
    throw "前端在 60 秒内没有就绪，请查看前端 CMD 窗口。"
}

if (-not $apiReady -or -not $frontendReady) {
    Write-Host "服务未能就绪，请查看新打开的终端窗口。" -ForegroundColor Red
    exit 1
}

Write-Host "前后端已启动，正在打开页面。" -ForegroundColor Green
Start-Process 'http://127.0.0.1:5173/#/create'
