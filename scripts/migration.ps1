# Legacy installation discovery and reversible aliases. Never read credential contents.
function Resolve-DybDirectory([string]$Path) {
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

function Get-DybMigrationPlan([string]$StateRoot, [string]$SkillsPath, [string]$RequestedWorkspace, [string]$LegacyStateDirectory) {
    $legacyState = if ($LegacyStateDirectory) { [IO.Path]::GetFullPath($LegacyStateDirectory) }
                   else { Join-Path (Split-Path -Parent $StateRoot) 'douyin-brain' }
    $aliases = @((Join-Path $SkillsPath 'douyin-brain'),
        (Join-Path $env:USERPROFILE '.codex\skills\douyin-brain'),
        (Join-Path $env:USERPROFILE '.agents\skills\douyin-brain'),
        (Join-Path $env:USERPROFILE '.claude\skills\douyin-brain'))
    if ($env:DSH_AGENTS_HOME) { $aliases += Join-Path $env:DSH_AGENTS_HOME 'skills\douyin-brain' }
    $files = @((Join-Path $StateRoot 'settings.json'), (Join-Path $legacyState 'settings.json'))
    $files += @($aliases | ForEach-Object { Join-Path $_ 'settings.json' })
    $candidates = @{}
    foreach ($file in @($files | Select-Object -Unique)) {
        if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { continue }
        $settings = Get-Content -LiteralPath $file -Raw -Encoding UTF8 | ConvertFrom-Json
        if (-not $settings.workspace) { throw ('Registered workspace is missing in ' + $file) }
        $path = Resolve-DybDirectory $settings.workspace
        if (-not (Test-Path -LiteralPath $path -PathType Container)) { throw ('Registered workspace no longer exists: ' + $path) }
        if (-not $candidates.ContainsKey($path)) {
            $runs = Join-Path $path 'runs'
            $count = if (Test-Path -LiteralPath $runs) { @(Get-ChildItem -LiteralPath $runs -Directory).Count } else { 0 }
            $candidates[$path] = @{workspace=$path;task_count=$count;credentials_present=(Test-Path -LiteralPath (Join-Path $path '.local\doubao.dpapi'));settings_files=@();legacy_skills=@()}
        }
        $candidates[$path].settings_files += $file
        if ($settings.skill_root -and (Split-Path -Leaf $settings.skill_root) -eq 'douyin-brain') {
            $candidates[$path].legacy_skills += $settings.skill_root
        }
    }
    $selected = if ($RequestedWorkspace) { Resolve-DybDirectory $RequestedWorkspace }
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
    }
    return @{workspace=$selected;choice_required=(-not $RequestedWorkspace -and $candidates.Count -gt 1);
        candidates=@($candidates.Values | Sort-Object workspace);selected=$record;backup=$null;aliases=@()}
}

function Backup-DybMigration([hashtable]$Plan, [string]$StateRoot) {
    if (-not $Plan.selected) { return }
    $folder = Join-Path $StateRoot ('backups\migration-' + (Get-Date -Format 'yyyy-MM-dd') + '-' + [Guid]::NewGuid().ToString('N').Substring(0,8))
    New-Item -ItemType Directory -Path $folder -Force | Out-Null
    $files = @($Plan.selected.settings_files) + @((Join-Path $Plan.workspace 'config.json'), (Join-Path $Plan.workspace 'AGENTS.md'))
    $saved = @()
    $n = 0
    foreach ($file in $files) {
        if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { continue }
        $n++
        $destination = Join-Path $folder ($n.ToString() + '-' + (Split-Path -Leaf $file))
        Copy-Item -LiteralPath $file -Destination $destination
        $saved += @{source=$file;backup=$destination}
    }
    $saved | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $folder 'files.json') -Encoding UTF8
    $Plan.backup = $folder
}

function Register-DybLegacyAliases([hashtable]$Plan, [string]$Target, [string]$StateRoot) {
    if (-not $Plan.selected) { return }
    $seen = @{}
    foreach ($alias in $Plan.selected.legacy_skills) {
        if (-not (Test-Path -LiteralPath (Join-Path $alias 'SKILL.md'))) { continue }
        $path = Resolve-DybDirectory $alias
        if ($seen.ContainsKey($path)) { continue }
        $seen[$path] = $true
        if ((Split-Path -Leaf $path) -ne 'douyin-brain') { throw 'Legacy alias target has an unexpected name; it was preserved.' }
        $parent = [IO.Path]::GetFullPath((Split-Path -Parent $path))
        if ((Split-Path -Parent $path) -ne $parent) { throw 'Legacy path is outside its recorded parent.' }
        $trash = [IO.Path]::GetFullPath((Join-Path (Split-Path -Parent $parent) '.trash'))
        $backup = [IO.Path]::GetFullPath((Join-Path $trash ((Get-Date -Format 'yyyy-MM-dd') + '_douyin-brain_' + [Guid]::NewGuid().ToString('N').Substring(0,8))))
        if (-not $backup.StartsWith($trash.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Legacy backup target is outside its root.' }
        New-Item -ItemType Directory -Path $trash -Force | Out-Null
        $dataInside = $Plan.workspace -eq $path -or $Plan.workspace.StartsWith($path.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)
        $entryFiles = @('SKILL.md', 'scripts\invoke.ps1')
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
            $skill = "---`nname: douyin-brain`ndescription: Compatibility entry for the installed dyb-douyinbrain Skill and existing workspace.`n---`n`nRead [$Target/SKILL.md]($($Target.Replace('\','/'))/SKILL.md) and follow that installed Skill. Invoke scripts/invoke.ps1 here to use the same workspace, credentials and tasks. Regular acquisition stays headless and never starts Computer Use.`n"
            [IO.File]::WriteAllText((Join-Path $path 'SKILL.md'), $skill, [Text.UTF8Encoding]::new($false))
            $entry = Join-Path $Target 'scripts\invoke.ps1'
            $forward = 'param([Parameter(ValueFromRemainingArguments=$true)][string[]]$BrainArgs)' + "`n" +
                '$ErrorActionPreference = ''Stop''' + "`n" +
                ('$env:DYB_STATE_DIR = ''' + $StateRoot.Replace("'","''") + "'`n") +
                ('& ''' + $entry.Replace("'","''") + ''' @BrainArgs') + "`nexit `$LASTEXITCODE`n"
            [IO.File]::WriteAllText((Join-Path $path 'scripts\invoke.ps1'), $forward, [Text.UTF8Encoding]::new($true))
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
