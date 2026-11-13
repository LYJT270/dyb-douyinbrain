param(
    [ValidateSet('auto','shared','deepseek','codex','claude','gemini','cursor','opencode','all','custom')]
    [string]$Agent = 'auto',
    [string]$StateDirectory,
    [string]$LegacyStateDirectory,
    [string]$SkillsRoot,
    [string]$DataDirectory,
    [string]$Workspace,
    [string]$Vault,
    [switch]$CreateVault,
    [string]$PythonExecutable,
    [switch]$NoApiWindow,
    [switch]$ConfigureSpeech,
    [switch]$SkipDependencies
)
$ErrorActionPreference = 'Stop'
$sourceRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$sourceItem = Get-Item -LiteralPath $sourceRoot
if ($sourceItem.Attributes -band [IO.FileAttributes]::ReparsePoint) {
    $sourceRoot = [IO.Path]::GetFullPath([string]($sourceItem.Target | Select-Object -First 1))
}
. (Join-Path $PSScriptRoot 'paths.ps1')
. (Join-Path $PSScriptRoot 'migration.ps1')
. (Join-Path $PSScriptRoot 'suite-install.ps1')
. (Join-Path $PSScriptRoot 'suite-guard.ps1')
if ($StateDirectory) { $env:CY_STATE_DIR = [IO.Path]::GetFullPath($StateDirectory) }
$stateRoot = Get-CyStateRoot
$explicitSkillsRoot = [bool]$SkillsRoot
$resultPath = Join-Path $stateRoot 'install-result.json'
$stage = 'verify_package'
$targetRoot = $null
$backupPath = $null
$discoveryLink = $null
$localEntryVerified = $false
$doctor = $null
$migration = $null
$suiteTransaction = $null
$suiteVerified = $false
$suiteRollback = $null
$installationLock = $null
$previousTransaction = $env:CY_SUITE_TRANSACTION

function Save-InstallResult([hashtable]$Value, [switch]$Quiet) {
    New-Item -ItemType Directory -Path $stateRoot -Force | Out-Null
    $Value.agent_target = $Agent
    $Value.updated_at = [DateTimeOffset]::Now.ToString('o')
    if ($env:CY_UPDATE_ID) { $Value.update_operation_id = $env:CY_UPDATE_ID }
    if ($targetRoot) {
        $Value.entrypoint = Join-Path $targetRoot 'scripts\invoke.ps1'
        $Value.skill_file = Join-Path $targetRoot 'SKILL.md'
        $Value.runtime_reference = Join-Path $targetRoot 'references\runtime.md'
        $Value.discovery_path = $targetRoot
        if ($discoveryLink) { $Value.claude_link = $discoveryLink }
    }
    if ($Workspace) { $Value.workspace_entry = Join-Path $Workspace 'AGENTS.md' }
    $Value.local_entry_verified = $localEntryVerified
    if ($suiteTransaction) {
        $Value.suite_transaction = $suiteTransaction.journal
        $Value.suite_verified = $suiteVerified
        $Value.suite_members = @($suiteTransaction.entries | ForEach-Object {
            @{name=$_.name;skill_file=(Join-Path $_.target 'SKILL.md');version=$suiteTransaction.version}
        })
    }
    if ($suiteRollback) { $Value.suite_rollback = $suiteRollback }
    if ($doctor) { $Value.execution_route = $doctor.execution_route }
    if ($migration) {
        $Value.migration = @{backup=$migration.backup;aliases=$migration.aliases;workspace=$migration.workspace}
    }
    if ($targetRoot) { $Value.onboarding_reference = Join-Path $targetRoot 'references\onboarding.md' }
    if ($doctor) { $Value.onboarding = $doctor.onboarding }
    $Value.welcome_command = 'welcome'
    $Value.next_action_for_agent = '读取 skill_file 和 onboarding_reference；用 entrypoint welcome 获取功能与可用状态，首次使用先在聊天展示再 welcome --acknowledge。按用户需求补配置和执行，不要求用户学命令；正文或分析先在聊天交付，文件作补充。'
    if ($Value.status -eq 'needs_workspace_choice') {
        $Value.next_action_for_agent = 'Ask the user once which candidate workspace to keep, then rerun with -Workspace. Do not merge workspaces.'
    }
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
    New-Item -ItemType Directory -Path $stateRoot -Force | Out-Null
    $installationLock = [IO.File]::Open((Join-Path $stateRoot 'install.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
    $manifest = Get-Content -LiteralPath (Join-Path $sourceRoot 'bundle.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($item in $manifest.file_sha256.PSObject.Properties) {
        $source = Resolve-CyPayloadFile $sourceRoot $item.Name
        if (-not (Test-Path -LiteralPath $source -PathType Leaf) -or
            (Get-ContentSha256 $source) -ne $item.Value) {
            throw ('迁移包文件缺失或校验不一致：' + $item.Name)
        }
    }
    $SkillsRoot = Get-CySkillsRoot $Agent $SkillsRoot
    $skillsPath = [IO.Path]::GetFullPath($SkillsRoot)
    $targetRoot = [IO.Path]::GetFullPath((Join-Path $skillsPath 'cy-charmyee'))
    $stage = 'discover_existing_workspaces'
    $migration = Get-CyMigrationPlan $stateRoot $skillsPath $Workspace $LegacyStateDirectory
    if ($migration.choice_required) {
        Save-InstallResult @{status='needs_workspace_choice';stage=$stage;candidates=$migration.candidates;live_asr_requests=0}
        exit 2
    }
    if ($migration.workspace) { $Workspace = $migration.workspace }
    $welcomeCatalog = Get-Content -LiteralPath (Join-Path $sourceRoot 'assets\capabilities.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $priorIntroduction = $null
    if ($Workspace -and (Test-Path -LiteralPath (Join-Path $Workspace '.local\onboarding.json'))) {
        try { $priorIntroduction = Get-Content -LiteralPath (Join-Path $Workspace '.local\onboarding.json') -Raw -Encoding UTF8 | ConvertFrom-Json } catch { $priorIntroduction = $null }
    }
    if (-not $priorIntroduction -or $priorIntroduction.presented_revision -ne $welcomeCatalog.revision) {
        Write-Output $welcomeCatalog.intro.zh
        foreach ($feature in $welcomeCatalog.capabilities) {
            Write-Output ($feature.zh.title + '：' + $feature.zh.example)
            Write-Output ('  ' + $feature.zh.outcome)
        }
        foreach ($note in $welcomeCatalog.notes.zh) { Write-Output $note }
    }
    Backup-CyMigration $migration $stateRoot
    if ((Split-Path -Parent $targetRoot) -ne $skillsPath.TrimEnd('\')) { throw '安装目标不在指定 skills 目录内。' }
    if (Test-Path -LiteralPath $targetRoot) {
        $targetItem = Get-Item -LiteralPath $targetRoot
        if ($targetItem.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            $linkedTarget = [string]($targetItem.Target | Select-Object -First 1)
            if (-not $linkedTarget) { throw 'Skill link has no resolvable target.' }
            $linkedTarget = [IO.Path]::GetFullPath($linkedTarget)
            $linkedManifest = Join-Path $linkedTarget 'bundle.json'
            if ((Split-Path -Leaf $linkedTarget) -ne 'cy-charmyee' -or
                -not (Test-Path -LiteralPath $linkedManifest) -or
                (Get-Content -LiteralPath $linkedManifest -Raw -Encoding UTF8 | ConvertFrom-Json).name -ne 'cy-charmyee') {
                throw 'The existing link does not point to a verified cy-charmyee install; it was preserved.'
            }
            $targetRoot = $linkedTarget
            $skillsPath = Split-Path -Parent $targetRoot
        }
    }
    $stage = 'install_suite'
    Start-CySuiteInstall $sourceRoot $targetRoot $stateRoot $manifest
    $null = Assert-CySuiteAvailable $targetRoot
    $suiteVerified = $true
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
        } else { $Workspace = Join-Path $DataDirectory 'cy-charmyee' }
    }
    $Workspace = [IO.Path]::GetFullPath($Workspace)
    $cfg = $null
    if (Test-Path -LiteralPath (Join-Path $Workspace 'config.json')) {
        $cfg = Get-Content -LiteralPath (Join-Path $Workspace 'config.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    }
    if (-not $Vault -and -not $cfg.vault_root -and $CreateVault) {
        $baseVault = Join-Path $DataDirectory 'cy-charmyee-知识库'
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
        Register-CyLegacyAliases $migration $targetRoot $stateRoot
        Complete-CySuiteInstall $suiteTransaction
        foreach ($entry in $suiteTransaction.entries) {
            $link = Register-CyClaudeLink $entry.target $Agent $explicitSkillsRoot
            if ($entry.name -eq 'cy-charmyee') { $discoveryLink = $link }
        }
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
    if (-not $doctor.doubao_credentials_present -and $ConfigureSpeech -and -not $NoApiWindow) {
        $stage = 'awaiting_api'
        Save-InstallResult @{status='awaiting_api';stage=$stage;skill=$targetRoot;version=$manifest.version;workspace=$Workspace;vault_root=$doctor.vault_root;backup=$backupPath}
        Write-Output '请在本机窗口填写豆包语音 API Key 并保存，安装器会自动检查，不需要回复已保存。'
        & $pythonPath -X utf8 $brainPath --workspace $Workspace configure
        if ($LASTEXITCODE -ne 0) { throw '本机凭据配置未成功。' }
        $doctor = Invoke-Brain $pythonPath $brainPath @('doctor') -AllowIncomplete
    }
    $status = if ($doctor.doubao_credentials_present) { 'installed' } else { 'awaiting_api' }
    $stage = 'legacy_aliases'
    Register-CyLegacyAliases $migration $targetRoot $stateRoot
    Complete-CySuiteInstall $suiteTransaction
    foreach ($entry in $suiteTransaction.entries) {
        $link = Register-CyClaudeLink $entry.target $Agent $explicitSkillsRoot
        if ($entry.name -eq 'cy-charmyee') { $discoveryLink = $link }
    }
    Save-InstallResult @{status=$status;stage='complete';skill=$targetRoot;version=$manifest.version;workspace=$Workspace;vault_root=$doctor.vault_root;checks=$doctor.checks;credentials_present=$doctor.doubao_credentials_present;doubao_api_status=$doctor.doubao_api_status;backup=$backupPath;live_asr_requests=0}
} catch {
    $failureMessage = $_.Exception.Message
    if ($suiteTransaction -and $suiteTransaction.status -ne 'committed') {
        try { Undo-CyMigration $migration }
        catch { $failureMessage += '; migration rollback: ' + $_.Exception.Message }
    }
    if ($suiteTransaction -and $suiteTransaction.status -notin @('committed','rolled_back')) {
        try {
            $suiteTransaction = Undo-CySuiteInstall $suiteTransaction
            $suiteRollback = @{status=$suiteTransaction.status;entries=$suiteTransaction.entries}
        } catch { $suiteRollback = @{status='failed';error=$_.Exception.Message} }
    }
    Save-InstallResult @{status='failed';stage=$stage;skill=$targetRoot;workspace=$Workspace;backup=$backupPath;error=$failureMessage;live_asr_requests=0}
    exit 1
} finally {
    if ($installationLock) { $installationLock.Dispose() }
    $env:CY_SUITE_TRANSACTION = $previousTransaction
}
