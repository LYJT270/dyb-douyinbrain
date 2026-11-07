param([Parameter(ValueFromRemainingArguments=$true)][string[]]$BrainArgs)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'paths.ps1')
. (Join-Path $PSScriptRoot 'suite-guard.ps1')
$null = Assert-DybSuiteAvailable (Split-Path -Parent $PSScriptRoot)
$settingsPath = Join-Path (Get-DybStateRoot) 'settings.json'
if (-not (Test-Path -LiteralPath $settingsPath)) { throw '尚未登记工作目录。Agent 应运行 scripts/install.ps1 完成配置，不改走网页识别。' }
$workspacePath = (Get-Content -LiteralPath $settingsPath -Raw -Encoding UTF8 | ConvertFrom-Json).workspace
$pythonPath = Join-Path $workspacePath '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw '运行环境不存在。Agent 应运行 scripts/install.ps1 修复本地环境，不改走网页识别。' }
& $pythonPath -B -X utf8 (Join-Path $PSScriptRoot 'brain.py') --workspace $workspacePath @BrainArgs
exit $LASTEXITCODE
