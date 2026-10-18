$ErrorActionPreference = 'Stop'

$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
$node = Get-Command node.exe -ErrorAction SilentlyContinue

function Find-OpenClaw {
    # npm's Windows global install normally creates openclaw.cmd. Some
    # distributions also expose an extensionless shim, while an .exe is not
    # guaranteed to exist at all.
    $command = Get-Command openclaw.cmd -ErrorAction SilentlyContinue
    if ($null -eq $command) {
        $command = Get-Command openclaw -ErrorAction SilentlyContinue
    }
    return $command
}

if ($null -eq $node -or $null -eq $npm) {
    throw '找不到 Node.js/npm。请先安装 Node.js 24.16+，再重新运行 install-openclaw-windows.bat。'
}

$nodeVersion = (& $node.Source '--version').Trim().TrimStart('v')
$nodeParts = $nodeVersion.Split('.')
$nodeMajor = [int]$nodeParts[0]
$nodeMinor = [int]$nodeParts[1]
if ($nodeMajor -lt 24 -or ($nodeMajor -eq 24 -and $nodeMinor -lt 16)) {
    throw "当前 Node.js 为 $nodeVersion。OpenClaw 最新版需要 Node.js 24.16+，请升级 Node.js 后重试。"
}

$openclaw = Find-OpenClaw
if ($null -ne $openclaw) {
    Write-Host "已找到 OpenClaw：$($openclaw.Source)" -ForegroundColor Green
    & $openclaw.Source '--version'
    exit $LASTEXITCODE
}

Write-Host '正在安装 OpenClaw（全局 npm 包）…' -ForegroundColor Cyan
& $npm.Source 'install' '--global' 'openclaw@latest'
if ($LASTEXITCODE -ne 0) {
    throw "OpenClaw 安装失败（退出码 $LASTEXITCODE）。请检查 npm 网络或权限。"
}

$openclaw = Find-OpenClaw
if ($null -eq $openclaw) {
    throw 'OpenClaw 已尝试安装，但当前窗口找不到 openclaw.cmd。请关闭窗口、重新打开后再运行。'
}

Write-Host 'OpenClaw 安装完成：' -ForegroundColor Green
& $openclaw.Source '--version'
