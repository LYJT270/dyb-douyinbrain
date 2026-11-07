param(
    [string]$Workspace,
    [string]$Vault,
    [switch]$CreateVault,
    [string]$AssistantRoot,
    [string]$PythonExecutable,
    [switch]$SkipBrowserInstall,
    [switch]$NoRegister,
    [switch]$NonInteractive,
    [switch]$SkipDependencies
)
$ErrorActionPreference = 'Stop'
$skillRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot 'paths.ps1')
$settingsPath = Join-Path (Get-DybStateRoot) 'settings.json'
if (-not $Workspace) {
    if (Test-Path -LiteralPath $settingsPath) {
        $Workspace = (Get-Content -LiteralPath $settingsPath -Raw -Encoding UTF8 | ConvertFrom-Json).workspace
    } else {
        $Workspace = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'dyb-douyinbrain'
    }
}
$workspacePath = [IO.Path]::GetFullPath($Workspace)

function Refresh-ProcessPath {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
        [Environment]::GetEnvironmentVariable('Path', 'User') + ';' +
        (Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Links') + ';' + $env:Path
}
function Install-UserPackage([string]$PackageId) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "缺少 WinGet。请先从 Microsoft Store 安装 App Installer，或手动安装 $PackageId 后重试。"
    }
    & winget install --id $PackageId --exact --source winget --scope user --accept-package-agreements --accept-source-agreements --silent
    if ($LASTEXITCODE -notin @(0, 3010)) { throw "$PackageId 安装未成功，退出码：$LASTEXITCODE" }
    Refresh-ProcessPath
}

if (-not $PythonExecutable) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        try {
            $candidate = & py -3.12 -c 'import sys; print(sys.executable)' 2>$null
            if ($LASTEXITCODE -eq 0) { $PythonExecutable = $candidate | Select-Object -Last 1 }
        } catch {
            $PythonExecutable = $null
        }
    }
    if (-not $PythonExecutable) {
        $candidate = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'
        if (Test-Path -LiteralPath $candidate) { $PythonExecutable = $candidate }
    }
    if (-not $PythonExecutable) {
        Install-UserPackage 'Python.Python.3.12'
        $candidate = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'
        if (Test-Path -LiteralPath $candidate) { $PythonExecutable = $candidate }
    }
}
if (-not $PythonExecutable -or -not (Test-Path -LiteralPath $PythonExecutable)) {
    throw '未找到 Python 3.12。安装完整 Python（含 pip、venv、Tk）后，使用 -PythonExecutable 指定路径。'
}
& $PythonExecutable -c 'import sys, tkinter, venv; assert sys.version_info >= (3,12)'
if ($LASTEXITCODE -ne 0) { throw '需要含 Tk、venv 的完整 Python 3.12 或更高版本。' }

$brainPath = Join-Path $PSScriptRoot 'brain.py'
$configPath = Join-Path $workspacePath 'config.json'
$configuredVault = $null
if (Test-Path -LiteralPath $configPath) {
    $configuredVault = (Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json).vault_root
}
if (-not $Vault -and -not $configuredVault) {
    if ($NonInteractive -and $CreateVault) {
        $baseVault = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'dyb-douyinbrain-知识库'
        $Vault = $baseVault
        $suffix = 2
        $knownLibrary = $false
        while (Test-Path -LiteralPath $Vault) {
            $knownLibrary = (Test-Path -LiteralPath (Join-Path $Vault 'AGENTS.md')) -and
                (Test-Path -LiteralPath (Join-Path $Vault 'SCHEMA.md')) -and
                (Test-Path -LiteralPath (Join-Path $Vault 'SOURCE_OF_TRUTH.md')) -and
                (Test-Path -LiteralPath (Join-Path $Vault 'index.md'))
            if ($knownLibrary -or -not (Get-ChildItem -LiteralPath $Vault -Force | Select-Object -First 1)) { break }
            $Vault = $baseVault + '-' + $suffix
            $suffix += 1
        }
        $CreateVault = -not $knownLibrary
        Write-Output ('自动配置知识库：' + $Vault)
    } elseif (-not $NonInteractive) {
        Write-Output '首次知识库配置：1 指定已有知识库；2 新建轻量 Markdown 知识库；3 稍后配置。'
        $vaultChoice = Read-Host '请选择 1、2 或 3'
        if ($vaultChoice -in @('1', '2')) {
            $Vault = Read-Host '请输入知识库完整目录（应与工作目录分开）'
            if (-not $Vault) { throw '知识库目录为空，未继续。' }
            if ($vaultChoice -eq '2') { $CreateVault = $true }
        } elseif ($vaultChoice -ne '3') {
            throw '未选择有效配置方式，未继续。'
        }
    }
}
if ($CreateVault -and $configuredVault -and $Vault -and
    ([IO.Path]::GetFullPath($configuredVault) -eq [IO.Path]::GetFullPath($Vault)) -and
    (Test-Path -LiteralPath $Vault)) {
    # Resume the same configured installation without recreating library rules.
    $CreateVault = $false
}
$initArgs = @('--workspace', $workspacePath, 'init')
if ($Vault) { $initArgs += @('--vault', $Vault) }
if ($CreateVault) { $initArgs += '--create-vault' }
if ($AssistantRoot) { $initArgs += @('--assistant', $AssistantRoot) }
if (-not $NoRegister) { $initArgs += '--register' }
& $PythonExecutable -X utf8 $brainPath @initArgs
if ($LASTEXITCODE -ne 0) { throw '工作目录或知识库配置失败，未继续安装。' }

if ($SkipDependencies) {
    Write-Output '仅完成隔离配置检查，运行依赖尚未安装。'
    return
}

$pythonPath = Join-Path $workspacePath '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    & $PythonExecutable -m venv (Join-Path $workspacePath '.venv')
    if ($LASTEXITCODE -ne 0) { throw '创建独立 Python 运行环境失败。' }
}
& $pythonPath -m pip install -r (Join-Path $PSScriptRoot 'runtime\requirements.lock.txt')
if ($LASTEXITCODE -ne 0) { throw '安装 Python 依赖失败，保留现场，可再次运行安装。' }

Refresh-ProcessPath
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue) -or -not (Get-Command ffprobe -ErrorAction SilentlyContinue)) {
    Install-UserPackage 'Gyan.FFmpeg'
}
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue) -or -not (Get-Command ffprobe -ErrorAction SilentlyContinue)) {
    throw 'FFmpeg/ffprobe 尚不可用，请核对安装结果和 PATH 后重试。'
}
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $workspacePath '.local\browsers'
if (-not $SkipBrowserInstall) {
    & $pythonPath -m playwright install chromium
    if ($LASTEXITCODE -ne 0) { throw 'Chromium 安装失败，未标记环境就绪。' }
}
& $pythonPath -X utf8 $brainPath --workspace $workspacePath doctor
if ($LASTEXITCODE -ne 0 -and -not $SkipBrowserInstall) { throw '环境检查未通过，请看缺失项。' }
if ($SkipBrowserInstall) { Write-Output '已跳过浏览器安装；抖音链接功能仍需补齐 Chromium。' }
Write-Output '依赖配置完成。语音 Key 请在本机配置；有凭据不代表真实识别已验证。'
Write-Output ('豆包手把手教程：' + (Join-Path $skillRoot '豆包配置教程.html'))
if ($NonInteractive) {
    Write-Output '环境准备完成。安装器将继续验证本地入口；语音凭据和知识库按任务需要配置，用户无需手动执行命令。'
} else {
    Write-Output '下一步：按教程开通语音极速版并取得 API Key，再双击“配置豆包.cmd”保存；首次实际任务通过随包程序调用豆包 API。'
}
