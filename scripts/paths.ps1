# Shared Windows path selection, independent of the model or Agent application.
$OutputEncoding = [Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)

function Get-DybStateRoot {
    if ($env:DYB_STATE_DIR) { return [IO.Path]::GetFullPath($env:DYB_STATE_DIR) }
    return Join-Path $env:LOCALAPPDATA 'dyb-douyinbrain'
}

function Get-DybSkillsRoot([string]$AgentName, [string]$Override) {
    if ($Override) { return [IO.Path]::GetFullPath($Override) }
    if ($AgentName -eq 'custom') { throw 'Custom Agent requires -SkillsRoot <directory>.' }
    if ($AgentName -eq 'claude') { return Join-Path $env:USERPROFILE '.claude\skills' }
    if ($AgentName -eq 'deepseek' -and $env:DSH_AGENTS_HOME) {
        return Join-Path ([IO.Path]::GetFullPath($env:DSH_AGENTS_HOME)) 'skills'
    }
    return Join-Path $env:USERPROFILE '.agents\skills'
}

function Register-DybClaudeLink([string]$Target, [string]$AgentName, [bool]$CustomRoot) {
    # A custom root is explicit and must not register into unrelated user directories.
    if ($CustomRoot -or $AgentName -notin @('auto','all')) { return $null }
    $claudeHome = Join-Path $env:USERPROFILE '.claude'
    if ($AgentName -eq 'auto' -and -not (Test-Path -LiteralPath $claudeHome)) { return $null }
    $link = Join-Path $claudeHome 'skills\dyb-douyinbrain'
    if (Test-Path -LiteralPath $link) {
        $item = Get-Item -LiteralPath $link
        $existing = [string]($item.Target | Select-Object -First 1)
        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -and $existing -and
            ([IO.Path]::GetFullPath($existing) -eq [IO.Path]::GetFullPath($Target))) { return $link }
        # Keep independent installations intact. The shared installation still succeeds.
        Write-Warning 'Claude has an independent dyb-douyinbrain installation; it was preserved. Update it with -Agent claude when needed.'
        return $null
    }
    New-Item -ItemType Directory -Path (Split-Path -Parent $link) -Force | Out-Null
    New-Item -ItemType Junction -Path $link -Target $Target | Out-Null
    return $link
}
