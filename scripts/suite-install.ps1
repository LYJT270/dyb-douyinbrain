# Transactional program installation. Workspace files are never moved by this module.
function Resolve-DybPayloadFile([string]$Root, [string]$Name) {
    # Archives/source hold child templates under skills/. Installed suites keep only sibling entries.
    $file = [IO.Path]::GetFullPath((Join-Path $Root $Name))
    if (-not $file.StartsWith([IO.Path]::GetFullPath($Root).TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) { throw '程序文件路径超出来源目录。' }
    if (Test-Path -LiteralPath $file -PathType Leaf) { return $file }
    if ((Test-Path -LiteralPath (Join-Path $Root '.dyb-suite.json')) -and $Name -match '^skills/(dyb-[a-z][a-z0-9-]*)/(.+)$') {
        $memberRoot = [IO.Path]::GetFullPath((Join-Path (Split-Path -Parent $Root) $Matches[1]))
        $memberFile = [IO.Path]::GetFullPath((Join-Path $memberRoot $Matches[2]))
        if (-not $memberFile.StartsWith($memberRoot.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) { throw '子 Skill 文件路径超出目录。' }
        return $memberFile
    }
    return $file
}

function Save-DybSuiteJournal($Transaction) {
    $temporary = $Transaction.journal + '.' + [Guid]::NewGuid().ToString('N') + '.tmp'
    $Transaction | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $temporary -Encoding UTF8
    Move-Item -LiteralPath $temporary -Destination $Transaction.journal -Force
}

function Assert-DybSuiteMove($Entry, $Transaction) {
    $root = [IO.Path]::GetFullPath($Transaction.skills_root).TrimEnd('\')
    $trash = [IO.Path]::GetFullPath((Join-Path (Split-Path -Parent $root) '.trash')).TrimEnd('\')
    if ($Entry.name -notmatch '^dyb-[a-z][a-z0-9-]*$' -or
        [IO.Path]::GetFullPath($Entry.target) -ne (Join-Path $root $Entry.name) -or
        [IO.Path]::GetFullPath((Split-Path -Parent $Entry.backup)) -ne $trash -or
        [IO.Path]::GetFullPath((Split-Path -Parent $Entry.failed_backup)) -ne $trash) {
        throw '套件移动路径超出已核对的安装或备份目录。'
    }
    foreach ($file in @($Entry.target, $Entry.backup)) {
        if ((Test-Path -LiteralPath $file) -and ((Get-Item -LiteralPath $file).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw '程序目录或备份为链接，保留现场，不移动链接目标。'
        }
    }
}

function Undo-DybSuiteInstall($Transaction, [switch]$IncludeCommitted) {
    if ($Transaction.status -eq 'rolled_back' -or ($Transaction.status -eq 'committed' -and -not $IncludeCommitted)) { return $Transaction }
    $Transaction.status = 'rolling_back'
    Save-DybSuiteJournal $Transaction
    foreach ($entry in @($Transaction.entries | Sort-Object order -Descending)) {
        if ($entry.state -eq 'pending' -or $entry.state -eq 'unchanged' -or $entry.state -eq 'restored') { continue }
        Assert-DybSuiteMove $entry $Transaction
        # A journal is persisted before each move. Existence resolves an interrupted move.
        if (Test-Path -LiteralPath $entry.backup) {
            if (Test-Path -LiteralPath $entry.target) {
                if (Test-Path -LiteralPath $entry.failed_backup) { throw '失败程序备份位置已有内容，保留现场。' }
                [IO.Directory]::Move($entry.target, $entry.failed_backup)
            }
            [IO.Directory]::Move($entry.backup, $entry.target)
        } elseif (-not $entry.had_existing -and (Test-Path -LiteralPath $entry.target)) {
            New-Item -ItemType Directory -Path (Split-Path -Parent $entry.failed_backup) -Force | Out-Null
            if (Test-Path -LiteralPath $entry.failed_backup) { throw '失败程序备份位置已有内容，保留现场。' }
            [IO.Directory]::Move($entry.target, $entry.failed_backup)
        } elseif ($entry.had_existing -and $entry.state -ne 'moving_old') {
            throw ('原程序备份缺失，未完成恢复：' + $entry.name)
        }
        $entry.state = 'restored'
        Save-DybSuiteJournal $Transaction
    }
    $Transaction.status = 'rolled_back'
    Save-DybSuiteJournal $Transaction
    $sentinel = Join-Path $Transaction.skills_root '.dyb-suite-installing.json'
    if ((Test-Path -LiteralPath $sentinel) -and
        (Get-Content -LiteralPath $sentinel -Raw -Encoding UTF8 | ConvertFrom-Json).id -eq $Transaction.id) {
        Remove-Item -LiteralPath $sentinel
    }
    return $Transaction
}

function Start-DybSuiteInstall([string]$Source, [string]$Target, [string]$StateRoot, $Manifest) {
    $skillsRoot = [IO.Path]::GetFullPath((Split-Path -Parent $Target))
    $journal = Join-Path $StateRoot 'suite-install.json'
    if (Test-Path -LiteralPath $journal) {
        $prior = Get-Content -LiteralPath $journal -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($prior.status -notin @('committed', 'rolled_back')) {
            if ([IO.Path]::GetFullPath($prior.skills_root) -ne $skillsRoot) { throw '另一安装位置有未恢复事务，请先恢复该位置。' }
            $null = Undo-DybSuiteInstall $prior
        }
    }
    $id = [Guid]::NewGuid().ToString('N')
    $stage = Join-Path $StateRoot ('suite-staging/' + $id)
    $trash = [IO.Path]::GetFullPath((Join-Path (Split-Path -Parent $skillsRoot) '.trash'))
    $stamp = (Get-Date -Format 'yyyy-MM-dd') + '_' + $id.Substring(0,8)
    $mainFiles = @($Manifest.file_sha256.PSObject.Properties.Name | Where-Object { -not ($Manifest.skill_suite -and $_.StartsWith('skills/')) })
    $specs = @(@{name='dyb-douyinbrain';source='';files=$mainFiles + @('bundle.json')})
    if ($Manifest.skill_suite) {
        if ($Manifest.skill_suite.schema -ne 1 -or $Manifest.skill_suite.product -ne 'dyb-douyinbrain') { throw '不支持的套件清单。' }
        $seen = @('dyb-douyinbrain')
        foreach ($member in $Manifest.skill_suite.members) {
            if ($member.name -notmatch '^dyb-[a-z][a-z0-9-]*$' -or $member.name -in $seen -or $member.source -ne ('skills/' + $member.name)) { throw '子 Skill 名称或来源无效。' }
            $prefix = $member.source + '/'
            $files = @($Manifest.file_sha256.PSObject.Properties.Name | Where-Object { $_.StartsWith($prefix) } | ForEach-Object { $_.Substring($prefix.Length) })
            foreach ($required in @('SKILL.md','agents/openai.yaml','scripts/invoke.ps1')) { if ($required -notin $files) { throw '子 Skill 缺少入口文件。' } }
            $specs += @{name=$member.name;source=$member.source;files=$files}
            $seen += $member.name
        }
    }
    $entries = @()
    $manifestHash = Get-ContentSha256 (Join-Path $Source 'bundle.json')
    foreach ($spec in $specs) {
        $destination = Join-Path $skillsRoot $spec.name
        $staged = Join-Path $stage $spec.name
        $entry = @{name=$spec.name;target=$destination;staged=$staged;order=$entries.Count;
                   backup=(Join-Path $trash ($stamp + '_' + $spec.name));
                   failed_backup=(Join-Path $trash ($stamp + '_failed_' + $spec.name));
                   had_existing=(Test-Path -LiteralPath $destination);state='pending'}
        $check = @{skills_root=$skillsRoot}
        Assert-DybSuiteMove $entry $check
        if ($entry.had_existing -and $spec.name -ne 'dyb-douyinbrain') {
            $markerFile = Join-Path $destination '.dyb-member.json'
            if (-not (Test-Path -LiteralPath $markerFile)) { throw ('同名目录未登记为本套件，已保留：' + $destination) }
            $marker = Get-Content -LiteralPath $markerFile -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($marker.product -ne 'dyb-douyinbrain' -or $marker.name -ne $spec.name) { throw '同名目录属于其他程序，已保留。' }
        }
        foreach ($name in $spec.files) {
            $logicalName = if ($spec.source) { $spec.source + '/' + $name } else { $name }
            $from = Resolve-DybPayloadFile $Source $logicalName
            $to = Join-Path $staged $name
            New-Item -ItemType Directory -Path (Split-Path -Parent $to) -Force | Out-Null
            Copy-Item -LiteralPath $from -Destination $to -Force
            if ($name -ne 'bundle.json') {
                $key = if ($spec.source) { $spec.source + '/' + $name } else { $name }
                if ((Get-ContentSha256 $to) -ne $Manifest.file_sha256.$key) { throw ('暂存文件校验失败：' + $key) }
            }
        }
        if ($Manifest.skill_suite) {
            $markerName = if ($spec.name -eq 'dyb-douyinbrain') { '.dyb-suite.json' } else { '.dyb-member.json' }
            [ordered]@{product='dyb-douyinbrain';name=$spec.name;version=$Manifest.version;manifest_sha256=$manifestHash} |
                ConvertTo-Json | Set-Content -LiteralPath (Join-Path $staged $markerName) -Encoding UTF8
        }
        $same = $entry.had_existing
        foreach ($file in Get-ChildItem -LiteralPath $staged -Recurse -File) {
            $name = $file.FullName.Substring($staged.Length).TrimStart('\')
            $current = Join-Path $destination $name
            if (-not (Test-Path -LiteralPath $current -PathType Leaf) -or (Get-ContentSha256 $current) -ne (Get-ContentSha256 $file.FullName)) { $same = $false; break }
        }
        if ($same) { $entry.state = 'unchanged' }
        if (-not $same -and (Test-Path -LiteralPath (Join-Path $destination '.git'))) { throw '安装目标是源码工作区，不能由安装包覆盖。' }
        $entries += $entry
    }
    $script:suiteTransaction = @{schema=1;id=$id;status='prepared';journal=$journal;skills_root=$skillsRoot;version=$Manifest.version;entries=$entries}
    Save-DybSuiteJournal $script:suiteTransaction
    New-Item -ItemType Directory -Path $skillsRoot -Force | Out-Null
    @{id=$id;journal=$journal} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $skillsRoot '.dyb-suite-installing.json') -Encoding UTF8
    $env:DYB_SUITE_TRANSACTION = $id
    $script:suiteTransaction.status = 'installing'
    Save-DybSuiteJournal $script:suiteTransaction
    $script:backupPath = if ($entries[0].had_existing -and $entries[0].state -ne 'unchanged') { $entries[0].backup } else { $null }
    Save-InstallResult @{status='installing';stage='install_suite';skill=$Target;version=$Manifest.version;workspace=$Workspace;backup=$script:backupPath;live_asr_requests=0} -Quiet
    foreach ($entry in $entries) {
        if ($entry.state -eq 'unchanged') { continue }
        Assert-DybSuiteMove $entry $script:suiteTransaction
        if ($entry.had_existing) {
            New-Item -ItemType Directory -Path $trash -Force | Out-Null
            $entry.state = 'moving_old'
            Save-DybSuiteJournal $script:suiteTransaction
            # Backup is a sibling on the same volume. Rename the directory as a unit:
            # Move-Item may fall back to a partial recursive move after a sharing violation.
            [IO.Directory]::Move($entry.target, $entry.backup)
        }
        $entry.state = 'installing_new'
        Save-DybSuiteJournal $script:suiteTransaction
        if ([IO.Path]::GetFullPath((Split-Path -Parent $entry.staged)) -ne [IO.Path]::GetFullPath($stage)) { throw '暂存程序路径无效。' }
        Move-Item -LiteralPath $entry.staged -Destination $entry.target
        $entry.state = 'installed'
        Save-DybSuiteJournal $script:suiteTransaction
    }
}

function Complete-DybSuiteInstall($Transaction) {
    $Transaction.status = 'committed'
    Save-DybSuiteJournal $Transaction
    $sentinel = Join-Path $Transaction.skills_root '.dyb-suite-installing.json'
    if ((Get-Content -LiteralPath $sentinel -Raw -Encoding UTF8 | ConvertFrom-Json).id -ne $Transaction.id) { throw '套件安装事务标识已改变。' }
    Remove-Item -LiteralPath $sentinel
}
