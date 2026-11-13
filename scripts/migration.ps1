# Legacy installation discovery and reversible aliases. Never read credential contents.
function Resolve-CyDirectory([string]$Path) {
    $resolved = [IO.Path]::GetFullPath($Path).TrimEnd('\')
    for ($n = 0; $n -lt 16 -and (Test-Path -LiteralPath $resolved); $n++) {
        $item = Get-Item -LiteralPath $resolved
        if (-not ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { break }
        $target = [string]($item.Target | Select-Object -First 1)
        if (-not $target) { throw 'Cannot resolve the legacy directory link.' }
        if (-not [IO.Path]::IsPathRooted($target)) { $target = Join-Path (Split-Path -Parent $resolved) $target }
        $next = [IO.Path]::GetFullPath($target).TrimEnd('\')
        if ($next -eq $resolved) { throw 'Circular legacy directory link.' }
        $resolved = $next
    }
    return $resolved
}

function Get-CyMigrationPlan([string]$StateRoot, [string]$SkillsPath, [string]$RequestedWorkspace, [string]$LegacyStateDirectory) {
    $legacyState = if ($LegacyStateDirectory) { [IO.Path]::GetFullPath($LegacyStateDirectory) }
                   else { Join-Path (Split-Path -Parent $StateRoot) 'douyin-brain' }
    # Inspect the chosen installation root; do not adopt other hosts' independent Skills.
    $aliases = @((Join-Path $SkillsPath 'douyin-brain'), (Join-Path $SkillsPath 'dyb-douyinbrain'))
    $files = @((Join-Path $StateRoot 'settings.json'), (Join-Path $legacyState 'settings.json'),
        (Join-Path (Split-Path -Parent $StateRoot) 'dyb-douyinbrain\settings.json'))
    $files += @($aliases | ForEach-Object { Join-Path $_ 'settings.json' })
    $candidates = @{}
    foreach ($file in @($files | Select-Object -Unique)) {
        if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { continue }
        $settings = Get-Content -LiteralPath $file -Raw -Encoding UTF8 | ConvertFrom-Json
        if (-not $settings.workspace) { throw ('Registered workspace is missing in ' + $file) }
        $path = Resolve-CyDirectory $settings.workspace
        if (-not (Test-Path -LiteralPath $path -PathType Container)) { throw ('Registered workspace no longer exists: ' + $path) }
        if (-not $candidates.ContainsKey($path)) {
            $runs = Join-Path $path 'runs'
            $count = if (Test-Path -LiteralPath $runs) { @(Get-ChildItem -LiteralPath $runs -Directory).Count } else { 0 }
            $candidates[$path] = @{workspace=$path;task_count=$count;credentials_present=(Test-Path -LiteralPath (Join-Path $path '.local\doubao.dpapi'));settings_files=@();legacy_skills=@()}
        }
        $candidates[$path].settings_files += $file
        if ($settings.skill_root -and (Split-Path -Leaf $settings.skill_root) -in @('douyin-brain','dyb-douyinbrain')) {
            $candidates[$path].legacy_skills += $settings.skill_root
        }
    }
    $selected = if ($RequestedWorkspace) { Resolve-CyDirectory $RequestedWorkspace }
                elseif ($candidates.Count -eq 1) { @($candidates.Keys)[0] } else { $null }
    $record = if ($selected -and $candidates.ContainsKey($selected)) { $candidates[$selected] } else { $null }
    # Do not adopt unrelated legacy code when the caller explicitly selects a new workspace.
    if ($record) {
        foreach ($alias in $aliases) {
            if (Test-Path -LiteralPath (Join-Path $alias 'SKILL.md')) {
                if ($candidates.Count -eq 1 -or $record.legacy_skills -contains $alias) { $record.legacy_skills += $alias }
            }
        }
        $record.legacy_skills = @($record.legacy_skills | Select-Object -Unique)
        foreach ($oldRoot in @($record.legacy_skills)) {
            $resolvedOld = Resolve-CyDirectory $oldRoot
            if ((Split-Path -Leaf $resolvedOld) -ne 'dyb-douyinbrain') { continue }
            $oldManifest = Join-Path $resolvedOld 'bundle.json'
            $oldBridge = Join-Path $resolvedOld '.cy-compat.json'
            if (Test-Path -LiteralPath $oldManifest) {
                $oldIdentity = Get-Content -LiteralPath $oldManifest -Raw -Encoding UTF8 | ConvertFrom-Json
                if ($oldIdentity.name -ne 'dyb-douyinbrain') { throw '旧版主入口的归属无法确认，已保留。' }
            } elseif (-not (Test-Path -LiteralPath $oldBridge)) { throw '旧版主入口缺少归属记录，已保留。' }
            $oldParent = Split-Path -Parent $resolvedOld
            if (Test-Path -LiteralPath (Join-Path $oldParent '.dyb-suite-installing.json')) {
                throw '旧版套件尚有未完成的安装，请先恢复该安装，再迁移到承意。'
            }
            foreach ($suffix in @('transcribe','analyze','download','write','knowledge','vault')) {
                $member = Join-Path $oldParent ('dyb-' + $suffix)
                if (-not (Test-Path -LiteralPath $member)) { continue }
                $marker = Join-Path $member '.dyb-member.json'
                $bridge = Join-Path $member '.cy-compat.json'
                if (Test-Path -LiteralPath $marker) {
                    $identity = Get-Content -LiteralPath $marker -Raw -Encoding UTF8 | ConvertFrom-Json
                    if ($identity.product -ne 'dyb-douyinbrain' -or $identity.name -ne ('dyb-' + $suffix)) {
                        throw ('旧子入口归属不一致，已保留：' + $member)
                    }
                } elseif (-not (Test-Path -LiteralPath $bridge)) { throw ('旧子入口缺少归属记录，已保留：' + $member) }
                $record.legacy_skills += $member
            }
        }
    }
    return @{workspace=$selected;choice_required=(-not $RequestedWorkspace -and $candidates.Count -gt 1);
        candidates=@($candidates.Values | Sort-Object workspace);selected=$record;backup=$null;aliases=@()}
}

function Backup-CyMigration([hashtable]$Plan, [string]$StateRoot) {
    if (-not $Plan.workspace) { return }
    $folder = Join-Path $StateRoot ('backups\migration-' + (Get-Date -Format 'yyyy-MM-dd') + '-' + [Guid]::NewGuid().ToString('N').Substring(0,8))
    New-Item -ItemType Directory -Path $folder -Force | Out-Null
    $files = @($Plan.selected.settings_files) + @((Join-Path $StateRoot 'settings.json'),
        (Join-Path $Plan.workspace 'config.json'), (Join-Path $Plan.workspace 'AGENTS.md'))
    $vaultState = Join-Path $Plan.workspace '.local\vault\state.json'
    if (Test-Path -LiteralPath $vaultState) {
        $files += $vaultState
        $savedState = Get-Content -LiteralPath $vaultState -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($savedState.hook.file) { $files += $savedState.hook.file }
    }
    $saved = @()
    $n = 0
    foreach ($file in @($files | Where-Object { $_ } | Select-Object -Unique)) {
        $n++
        $destination = Join-Path $folder ($n.ToString() + '-' + (Split-Path -Leaf $file))
        $exists = Test-Path -LiteralPath $file -PathType Leaf
        if ($exists) { Copy-Item -LiteralPath $file -Destination $destination }
        $saved += @{source=$file;backup=$destination;existed=$exists}
    }
    $saved | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $folder 'files.json') -Encoding UTF8
    $Plan.backup = $folder
}

function Register-CyLegacyAliases([hashtable]$Plan, [string]$Target, [string]$StateRoot) {
    if (-not $Plan.selected) { return }
    $seen = @{}
    foreach ($alias in $Plan.selected.legacy_skills) {
        if (-not (Test-Path -LiteralPath (Join-Path $alias 'SKILL.md'))) { continue }
        $path = Resolve-CyDirectory $alias
        if ($seen.ContainsKey($path)) { continue }
        $seen[$path] = $true
        $name = Split-Path -Leaf $path
        if ($name -notin @('douyin-brain','dyb-douyinbrain','dyb-transcribe','dyb-analyze','dyb-download','dyb-write','dyb-knowledge','dyb-vault')) {
            throw 'Legacy alias target has an unexpected name; it was preserved.'
        }
        $destination = if ($name -in @('douyin-brain','dyb-douyinbrain')) { $Target }
                       else { Join-Path (Split-Path -Parent $Target) ($name -replace '^dyb-', 'cy-') }
        if (Test-Path -LiteralPath (Join-Path $path '.git')) { throw '源码仓库不能转换为兼容入口；请使用独立安装目录。' }
        $parent = [IO.Path]::GetFullPath((Split-Path -Parent $path))
        if ((Split-Path -Parent $path) -ne $parent) { throw 'Legacy path is outside its recorded parent.' }
        $trash = [IO.Path]::GetFullPath((Join-Path (Split-Path -Parent $parent) '.trash'))
        $backup = [IO.Path]::GetFullPath((Join-Path $trash ((Get-Date -Format 'yyyy-MM-dd') + '_' + $name + '_' + [Guid]::NewGuid().ToString('N').Substring(0,8))))
        if (-not $backup.StartsWith($trash.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Legacy backup target is outside its root.' }
        New-Item -ItemType Directory -Path $trash -Force | Out-Null
        $dataInside = $Plan.workspace -eq $path -or $Plan.workspace.StartsWith($path.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)
        $entryFiles = @('SKILL.md', 'scripts\invoke.ps1', '.cy-compat.json', 'agents\openai.yaml')
        if ($dataInside) {
            # Legacy portable installs can keep their workspace inside the Skill.
            # Preserve that directory and back up only the two forwarding entries.
            foreach ($relative in $entryFiles) {
                $original = Join-Path $path $relative
                if (Test-Path -LiteralPath $original -PathType Leaf) {
                    $saved = Join-Path $backup $relative
                    New-Item -ItemType Directory -Path (Split-Path -Parent $saved) -Force | Out-Null
                    Copy-Item -LiteralPath $original -Destination $saved
                }
            }
        } else {
            Move-Item -LiteralPath $path -Destination $backup
        }
        try {
            New-Item -ItemType Directory -Path (Join-Path $path 'scripts') -Force | Out-Null
            $skill = "---`nname: $name`ndescription: Legacy compatibility entry. Use the corresponding CY-CharmYee Skill for new requests.`n---`n`nRead [承意 CY-CharmYee]($($destination.Replace('\','/'))/SKILL.md) and follow that installed Skill. Invoke scripts/invoke.ps1 here to use the same workspace, credentials and tasks. Regular acquisition stays headless and never starts Computer Use.`n"
            [IO.File]::WriteAllText((Join-Path $path 'SKILL.md'), $skill, [Text.UTF8Encoding]::new($false))
            $entry = Join-Path $destination 'scripts\invoke.ps1'
            $forward = 'param([Parameter(ValueFromRemainingArguments=$true)][string[]]$BrainArgs)' + "`n" +
                '$ErrorActionPreference = ''Stop''' + "`n" +
                ('$env:CY_STATE_DIR = ''' + $StateRoot.Replace("'","''") + "'`n") +
                ('& ''' + $entry.Replace("'","''") + ''' @BrainArgs') + "`nexit `$LASTEXITCODE`n"
            [IO.File]::WriteAllText((Join-Path $path 'scripts\invoke.ps1'), $forward, [Text.UTF8Encoding]::new($true))
            @{product='cy-charmyee';legacy_name=$name;target=$destination} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $path '.cy-compat.json') -Encoding UTF8
            New-Item -ItemType Directory -Path (Join-Path $path 'agents') -Force | Out-Null
            [IO.File]::WriteAllText((Join-Path $path 'agents\openai.yaml'), "policy:`n  allow_implicit_invocation: false`n", [Text.UTF8Encoding]::new($false))
            $Plan.aliases += @{path=$path;backup=$backup;entrypoint=$entry;workspace_preserved_in_place=$dataInside}
        } catch {
            # Preserve the failed bridge and restore the verified original directory.
            $failed = Join-Path $trash ((Split-Path -Leaf $backup) + '-failed-bridge')
            if ($dataInside) {
                foreach ($relative in $entryFiles) {
                    $original = Join-Path $path $relative
                    if (Test-Path -LiteralPath $original -PathType Leaf) {
                        $failedFile = Join-Path $failed $relative
                        New-Item -ItemType Directory -Path (Split-Path -Parent $failedFile) -Force | Out-Null
                        Move-Item -LiteralPath $original -Destination $failedFile
                    }
                    $saved = Join-Path $backup $relative
                    if (Test-Path -LiteralPath $saved -PathType Leaf) { Copy-Item -LiteralPath $saved -Destination $original }
                }
            } else {
                if (Test-Path -LiteralPath $path) { Move-Item -LiteralPath $path -Destination $failed }
                Move-Item -LiteralPath $backup -Destination $path
            }
            throw
        }
    }
}

function Undo-CyMigration([hashtable]$Plan) {
    if (-not $Plan) { return }
    $aliases = @($Plan.aliases)
    [array]::Reverse($aliases)
    foreach ($alias in $aliases) {
        $path = [IO.Path]::GetFullPath($alias.path)
        $backup = [IO.Path]::GetFullPath($alias.backup)
        $trash = [IO.Path]::GetFullPath((Join-Path (Split-Path -Parent (Split-Path -Parent $path)) '.trash'))
        if ((Split-Path -Parent $backup) -ne $trash) { throw '兼容入口回滚目录不在已验证的备份目录。' }
        $failed = $backup + '-failed-bridge'
        if ($alias.workspace_preserved_in_place) {
            foreach ($relative in @('SKILL.md','scripts\invoke.ps1','.cy-compat.json','agents\openai.yaml')) {
                $original = Join-Path $path $relative
                if (Test-Path -LiteralPath $original -PathType Leaf) {
                    $saved = Join-Path $failed $relative
                    New-Item -ItemType Directory -Path (Split-Path -Parent $saved) -Force | Out-Null
                    Move-Item -LiteralPath $original -Destination $saved
                }
                $saved = Join-Path $backup $relative
                if (Test-Path -LiteralPath $saved) { Copy-Item -LiteralPath $saved -Destination $original }
            }
        } else {
            if (Test-Path -LiteralPath $path) { Move-Item -LiteralPath $path -Destination $failed }
            Move-Item -LiteralPath $backup -Destination $path
        }
    }
    if ($Plan.backup) {
        $files = Get-Content -LiteralPath (Join-Path $Plan.backup 'files.json') -Raw -Encoding UTF8 | ConvertFrom-Json
        foreach ($file in $files) {
            if ($file.existed) { Copy-Item -LiteralPath $file.backup -Destination $file.source -Force }
            elseif (Test-Path -LiteralPath $file.source -PathType Leaf) {
                Move-Item -LiteralPath $file.source -Destination ($file.backup + '-created-during-failed-install')
            }
        }
    }
}
