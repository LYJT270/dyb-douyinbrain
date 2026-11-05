param(
    [ValidateSet('auto','shared','deepseek','codex','claude','gemini','cursor','opencode','all','custom')]
    [string]$Agent = 'auto',
    [string]$StateDirectory,
    [string]$SkillsRoot,
    [string]$DataDirectory,
    [string]$Workspace,
    [string]$Vault,
    [switch]$CreateVault,
    [string]$PythonExecutable,
    [switch]$NoApiWindow,
    [switch]$SkipDependencies
)
$ErrorActionPreference = 'Stop'
$sourceRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$sourceItem = Get-Item -LiteralPath $sourceRoot
if ($sourceItem.Attributes -band [IO.FileAttributes]::ReparsePoint) {
    $sourceRoot = [IO.Path]::GetFullPath([string]($sourceItem.Target | Select-Object -First 1))
}
. (Join-Path $PSScriptRoot 'paths.ps1')
if ($StateDirectory) { $env:DYB_STATE_DIR = [IO.Path]::GetFullPath($StateDirectory) }
$stateRoot = Get-DybStateRoot
$explicitSkillsRoot = [bool]$SkillsRoot
$resultPath = Join-Path $stateRoot 'install-result.json'
$stage = 'verify_package'
$targetRoot = $null
$backupPath = $null
$discoveryLink = $null
$localEntryVerified = $false
$doctor = $null

function Save-InstallResult([hashtable]$Value, [switch]$Quiet) {
    New-Item -ItemType Directory -Path $stateRoot -Force | Out-Null
    $Value.agent_target = $Agent
    $Value.updated_at = [DateTimeOffset]::Now.ToString('o')
    if ($env:DYB_UPDATE_ID) { $Value.update_operation_id = $env:DYB_UPDATE_ID }
    if ($targetRoot) {
        $Value.entrypoint = Join-Path $targetRoot 'scripts\invoke.ps1'
        $Value.skill_file = Join-Path $targetRoot 'SKILL.md'
        $Value.runtime_reference = Join-Path $targetRoot 'references\runtime.md'
        $Value.discovery_path = $targetRoot
        if ($discoveryLink) { $Value.claude_link = $discoveryLink }
    }
    if ($Workspace) { $Value.workspace_entry = Join-Path $Workspace 'AGENTS.md' }
    $Value.local_entry_verified = $localEntryVerified
    if ($doctor) { $Value.execution_route = $doctor.execution_route }
    $Value.next_action_for_agent = '立即读取 skill_file 和 runtime_reference，在当前对话使用 entrypoint；媒体转写走随包程序及豆包 API，缺项先修复，不自行转到网页识别。'
    $temporaryResult = $resultPath + '.' + [Guid]::NewGuid().ToString('N') + '.tmp'
    $Value | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $temporaryResult -Encoding UTF8
    Move-Item -LiteralPath $temporaryResult -Destination $resultPath -Force
    if (-not $Quiet) { $Value | ConvertTo-Json -Depth 12 | Write-Output }
}
function Get-ContentSha256([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace('-', '').ToLowerInvariant() }
    finally { $stream.Dispose(); $algorithm.Dispose() }
}
function Invoke-Brain([string]$PythonPath, [string]$BrainPath, [string[]]$CommandArgs, [switch]$AllowIncomplete) {
    $lines = & $PythonPath -X utf8 $BrainPath --workspace $Workspace @CommandArgs
    $code = $LASTEXITCODE
    $value = ($lines -join "`n") | ConvertFrom-Json
    if ($code -ne 0 -and -not $AllowIncomplete) { throw ($value | ConvertTo-Json -Compress -Depth 6) }
    return $value
}
try {
    $manifest = Get-Content -LiteralPath (Join-Path $sourceRoot 'bundle.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($item in $manifest.file_sha256.PSObject.Properties) {
        $source = [IO.Path]::GetFullPath((Join-Path $sourceRoot $item.Name))
        if (-not $source.StartsWith($sourceRoot.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) {
            throw '迁移包清单包含超出程序目录的路径。'
        }
        if (-not (Test-Path -LiteralPath $source -PathType Leaf) -or
            (Get-ContentSha256 $source) -ne $item.Value) {
            throw ('迁移包文件缺失或校验不一致：' + $item.Name)
        }
    }
    $SkillsRoot = Get-DybSkillsRoot $Agent $SkillsRoot
    $skillsPath = [IO.Path]::GetFullPath($SkillsRoot)
    $targetRoot = [IO.Path]::GetFullPath((Join-Path $skillsPath 'dyb-douyinbrain'))
    if ((Split-Path -Parent $targetRoot) -ne $skillsPath.TrimEnd('\')) { throw '安装目标不在指定 skills 目录内。' }
    if (Test-Path -LiteralPath $targetRoot) {
        $targetItem = Get-Item -LiteralPath $targetRoot
        if ($targetItem.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            $linkedTarget = [string]($targetItem.Target | Select-Object -First 1)
            if (-not $linkedTarget) { throw 'Skill link has no resolvable target.' }
            $linkedTarget = [IO.Path]::GetFullPath($linkedTarget)
            $linkedManifest = Join-Path $linkedTarget 'bundle.json'
            if ((Split-Path -Leaf $linkedTarget) -ne 'dyb-douyinbrain' -or
                -not (Test-Path -LiteralPath $linkedManifest) -or
                (Get-Content -LiteralPath $linkedManifest -Raw -Encoding UTF8 | ConvertFrom-Json).name -ne 'dyb-douyinbrain') {
                throw 'The existing link does not point to a verified dyb-douyinbrain install; it was preserved.'
            }
            $targetRoot = $linkedTarget
            $skillsPath = Split-Path -Parent $targetRoot
        }
    }
    if ($sourceRoot -ne $targetRoot) {
        $stage = 'install_skill'
        if (Test-Path -LiteralPath $targetRoot) {
            if ((Get-Item -LiteralPath $targetRoot).Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw '同名安装目录为链接，请由 Agent 核对其真实维护位置后继续，不能直接覆盖。'
            }
            $same = $true
            foreach ($item in $manifest.file_sha256.PSObject.Properties) {
                $existing = Join-Path $targetRoot $item.Name
                if (-not (Test-Path -LiteralPath $existing -PathType Leaf) -or
                    (Get-ContentSha256 $existing) -ne $item.Value) { $same = $false; break }
            }
            if (-not $same) {
                $backupRoot = [IO.Path]::GetFullPath((Join-Path (Split-Path -Parent $skillsPath) '.trash'))
                $backupPath = [IO.Path]::GetFullPath((Join-Path $backupRoot ((Get-Date -Format 'yyyy-MM-dd') + '_dyb-douyinbrain_' + [Guid]::NewGuid().ToString('N').Substring(0,8))))
                if (-not $backupPath.StartsWith($backupRoot.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) { throw '备份目标超出允许目录。' }
                # Both absolute move targets were checked against the explicitly named roots above.
                New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
                Save-InstallResult @{status='installing';stage='backup_skill';skill=$targetRoot;version=$manifest.version;workspace=$Workspace;backup=$backupPath} -Quiet
                Move-Item -LiteralPath $targetRoot -Destination $backupPath
            }
        }
        New-Item -ItemType Directory -Path $targetRoot -Force | Out-Null
        foreach ($name in @($manifest.file_sha256.PSObject.Properties.Name) + @('bundle.json')) {
            $destination = Join-Path $targetRoot $name
            New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
            Copy-Item -LiteralPath (Join-Path $sourceRoot $name) -Destination $destination -Force
        }
    }
    $discoveryLink = Register-DybClaudeLink $targetRoot $Agent $explicitSkillsRoot
    $stage = 'configure_workspace'
    if (-not $DataDirectory) {
        $DataDirectory = [Environment]::GetFolderPath('MyDocuments')
        if (-not $DataDirectory) { $DataDirectory = Join-Path $env:USERPROFILE 'Documents' }
    }
    $DataDirectory = [IO.Path]::GetFullPath($DataDirectory)
    if (-not $Workspace) {
        $settings = Join-Path $stateRoot 'settings.json'
        if (Test-Path -LiteralPath $settings) {
            $Workspace = (Get-Content -LiteralPath $settings -Raw -Encoding UTF8 | ConvertFrom-Json).workspace
        } else { $Workspace = Join-Path $DataDirectory 'dyb-douyinbrain' }
    }
    $Workspace = [IO.Path]::GetFullPath($Workspace)
    $cfg = $null
    if (Test-Path -LiteralPath (Join-Path $Workspace 'config.json')) {
        $cfg = Get-Content -LiteralPath (Join-Path $Workspace 'config.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    }
    if (-not $Vault -and -not $cfg.vault_root) {
        $baseVault = Join-Path $DataDirectory 'dyb-douyinbrain-知识库'
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
    }
    $stage = 'install_dependencies'
    $setupParams = @{Workspace=$Workspace;NonInteractive=$true}
    if ($Vault) { $setupParams.Vault = $Vault }
    if ($CreateVault) { $setupParams.CreateVault = $true }
    if ($PythonExecutable) { $setupParams.PythonExecutable = $PythonExecutable }
    if ($SkipDependencies) { $setupParams.SkipDependencies = $true }
    & (Join-Path $targetRoot 'scripts\setup.ps1') @setupParams
    $pythonPath = Join-Path $Workspace '.venv\Scripts\python.exe'
    if ($SkipDependencies) { $pythonPath = $PythonExecutable }
    if (-not $pythonPath -or -not (Test-Path -LiteralPath $pythonPath)) { throw '运行环境未生成，不能标记安装完成。' }
    $brainPath = Join-Path $targetRoot 'scripts\brain.py'
    $stage = 'environment_check'
    $doctor = Invoke-Brain $pythonPath $brainPath @('doctor') -AllowIncomplete
    if ($SkipDependencies) {
        Save-InstallResult @{status='dependencies_pending';stage=$stage;skill=$targetRoot;version=$manifest.version;workspace=$Workspace;vault_root=$doctor.vault_root;checks=$doctor.checks;test_mode=$true;backup=$backupPath;doubao_api_status='not_checked'}
        exit 0
    }
    if ($doctor.status -ne 'environment_ready') { throw '依赖检查未通过，Agent 应按缺失项继续修复，不能让用户手动补命令。' }
    $stage = 'verify_local_entry'
    $entryLines = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $targetRoot 'scripts\invoke.ps1') doctor
    if ($LASTEXITCODE -ne 0) { throw '已安装的本地执行入口未通过检查，应修复入口，不能改走网页识别。' }
    $entryDoctor = ($entryLines -join "`n") | ConvertFrom-Json
    $expectedResource = [IO.Path]::GetFullPath((Join-Path $targetRoot 'scripts\runtime'))
    $localEntryVerified = ($entryDoctor.status -eq 'environment_ready') -and
        ([IO.Path]::GetFullPath($entryDoctor.resource_root) -eq $expectedResource) -and
        ([IO.Path]::GetFullPath($entryDoctor.workspace) -eq $Workspace) -and
        ($entryDoctor.execution_route.asr_provider -eq 'doubao_voice_api') -and
        ($entryDoctor.execution_route.web_transcription_fallback -eq $false)
    if (-not $localEntryVerified) { throw '本地入口、工作目录或豆包执行路线不一致，未完成安装。' }
    if (-not $doctor.doubao_credentials_present -and -not $NoApiWindow) {
        $stage = 'awaiting_api'
        Save-InstallResult @{status='awaiting_api';stage=$stage;skill=$targetRoot;version=$manifest.version;workspace=$Workspace;vault_root=$doctor.vault_root;backup=$backupPath}
        Write-Output '请在本机窗口填写豆包语音 API Key 并保存，安装器会自动检查，不需要回复已保存。'
        & $pythonPath -X utf8 $brainPath --workspace $Workspace configure
        if ($LASTEXITCODE -ne 0) { throw '本机凭据配置未成功。' }
        $doctor = Invoke-Brain $pythonPath $brainPath @('doctor') -AllowIncomplete
    }
    $status = if ($doctor.doubao_credentials_present) { 'installed' } else { 'awaiting_api' }
    Save-InstallResult @{status=$status;stage='complete';skill=$targetRoot;version=$manifest.version;workspace=$Workspace;vault_root=$doctor.vault_root;checks=$doctor.checks;credentials_present=$doctor.doubao_credentials_present;doubao_api_status=$doctor.doubao_api_status;backup=$backupPath;live_asr_requests=0}
} catch {
    Save-InstallResult @{status='failed';stage=$stage;skill=$targetRoot;workspace=$Workspace;backup=$backupPath;error=$_.Exception.Message;live_asr_requests=0}
    exit 1
}
