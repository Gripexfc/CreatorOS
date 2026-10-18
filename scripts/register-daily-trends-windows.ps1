param(
    [string]$Time = '08:00'
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$fetchScript = Join-Path $root 'scripts\fetch-trends-windows.ps1'
$taskName = 'CreatorOS Daily Trends'

if (-not (Test-Path -LiteralPath $fetchScript)) {
    throw "找不到每日热点脚本：$fetchScript"
}

try {
    $at = [datetime]::ParseExact($Time, 'HH:mm', [Globalization.CultureInfo]::InvariantCulture)
}
catch {
    throw "时间格式应为 HH:mm，例如 08:00 或 21:30。"
}

$userId = if ($env:USERDOMAIN) { "$($env:USERDOMAIN)\$($env:USERNAME)" } else { $env:USERNAME }
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument (
    "-NoProfile -ExecutionPolicy Bypass -File `"$fetchScript`""
)
$trigger = New-ScheduledTaskTrigger -Daily -At $at
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId $userId -LogonType Interactive -RunLevel Limited

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description '每天抓取 CreatorOS 抖音、微博和知乎公开热点榜单并写入本地缓存。' `
    -Force | Out-Null

Write-Host "已注册 Windows 任务：$taskName" -ForegroundColor Green
Write-Host "执行时间：每天 $Time（当前用户登录后运行，错过时间会在下次登录时补跑）"
Write-Host "现在先执行一次抓取…" -ForegroundColor Cyan

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $fetchScript
if ($LASTEXITCODE -ne 0) {
    Write-Host "首次抓取未成功，但每日任务仍已注册；请查看 runtime\logs 中的日志。" -ForegroundColor Yellow
}
