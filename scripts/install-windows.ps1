$ErrorActionPreference = 'Stop'

$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$venvPython = Join-Path $root '.venv312\Scripts\python.exe'
$frontend = Join-Path $root 'web\frontend'
Push-Location $root

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $false)][string[]]$ArgumentList = @()
    )

    & $FilePath @ArgumentList
    if ($LASTEXITCODE -ne 0) {
        throw "命令失败（退出码 $LASTEXITCODE）：$FilePath $($ArgumentList -join ' ')"
    }
}

function Find-CommandPath {
    param([Parameter(Mandatory = $true)][string]$Name)

    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($null -eq $command) {
        return $null
    }
    return $command.Source
}

try {
    Write-Host "CreatorOS Windows 安装程序" -ForegroundColor Cyan
    Write-Host "项目目录：$root"

    $node = Find-CommandPath 'node.exe'
    $npm = Find-CommandPath 'npm.cmd'
    if ($null -eq $node -or $null -eq $npm) {
        throw "找不到 Node.js/npm。请先安装 Node.js 24.16+（https://nodejs.org/），然后重新双击 install-windows.bat。"
    }

    $nodeVersion = (& $node '--version').Trim()
    $nodeParts = $nodeVersion.TrimStart('v').Split('.')
    $nodeMajor = [int]$nodeParts[0]
    $nodeMinor = [int]$nodeParts[1]
    if ($nodeMajor -lt 24 -or ($nodeMajor -eq 24 -and $nodeMinor -lt 16)) {
        throw "模型服务需要 Node.js 24.16+，当前版本为 $nodeVersion。请升级 Node.js 后重新运行。"
    }

    $uv = Find-CommandPath 'uv.exe'
    if ($null -eq $uv) {
        $pythonLauncher = Find-CommandPath 'py.exe'
        $python = Find-CommandPath 'python.exe'
        if ($null -eq $pythonLauncher -and $null -eq $python) {
            throw "找不到 Python。请安装 Python 3.12（https://www.python.org/downloads/），并勾选 Add Python to PATH，然后重新运行。"
        }

        Write-Host "未找到 uv，正在用 Python 安装到当前用户目录…" -ForegroundColor Yellow
        if ($null -ne $pythonLauncher) {
            # uv 会在下一步负责寻找或下载 Python 3.12；这里使用系统默认
            # Python 只负责把 uv 安装到当前用户目录。
            Invoke-Checked $pythonLauncher @('-m', 'pip', 'install', '--user', 'uv')
            $userBase = (& $pythonLauncher '-m' 'site' '--user-base').Trim()
        }
        else {
            Invoke-Checked $python @('-m', 'pip', 'install', '--user', 'uv')
            $userBase = (& $python '-m' 'site' '--user-base').Trim()
        }

        $candidate = Join-Path $userBase 'Scripts\uv.exe'
        if (Test-Path $candidate) {
            $uv = $candidate
        }
        else {
            $uv = Find-CommandPath 'uv.exe'
        }
        if ($null -eq $uv) {
            throw "uv 已尝试安装，但当前窗口找不到它。请关闭此窗口、重新双击 install-windows.bat；若仍失败，请把用户 Python Scripts 目录加入 PATH。"
        }
    }

    if (-not (Test-Path $venvPython)) {
        Write-Host "正在创建 Python 3.12 虚拟环境…" -ForegroundColor Yellow
        Invoke-Checked $uv @('venv', '--python', '3.12', (Join-Path $root '.venv312'))
    }

    Write-Host "正在安装后端依赖…" -ForegroundColor Yellow
    Invoke-Checked $uv @('pip', 'install', '--python', $venvPython, '-e', '.[dev]')

    Write-Host "正在安装前端依赖…" -ForegroundColor Yellow
    Push-Location $frontend
    try {
        Invoke-Checked $npm @('ci')
    }
    finally {
        Pop-Location
    }

    # OpenClaw is part of the normal Windows setup. Keeping this in the main
    # installer avoids a half-installed state where the web app starts but
    # every real generation is blocked by a missing local gateway.
    $openclawInstaller = Join-Path $root 'scripts\install-openclaw-windows.ps1'
    if (Test-Path $openclawInstaller) {
        Write-Host "正在安装模型服务 OpenClaw…" -ForegroundColor Yellow
        Invoke-Checked 'powershell.exe' @(
            '-NoProfile',
            '-ExecutionPolicy',
            'Bypass',
            '-File',
            $openclawInstaller
        )
    }

    Write-Host ""
    Write-Host "安装完成。以后双击项目根目录的 start-all-windows.bat 即可启动。" -ForegroundColor Green
    Write-Host "浏览器地址：http://127.0.0.1:5173/#/create"
}
catch {
    Write-Host ""
    Write-Host "安装失败：$($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
finally {
    Pop-Location
}
