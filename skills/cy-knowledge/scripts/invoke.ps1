param([Parameter(ValueFromRemainingArguments=$true)][string[]]$BrainArgs)
$ErrorActionPreference = 'Stop'
$memberRoot = Split-Path -Parent $PSScriptRoot
$memberItem = Get-Item -LiteralPath $memberRoot
if ($memberItem.Attributes -band [IO.FileAttributes]::ReparsePoint) {
    $memberRoot = [IO.Path]::GetFullPath([string]($memberItem.Target | Select-Object -First 1))
}
$container = Split-Path -Parent $memberRoot
$candidates = @((Join-Path $container 'cy-charmyee'), (Split-Path -Parent $container))
try {
    $shared = $null
    foreach ($candidate in $candidates) {
        $manifestFile = Join-Path $candidate 'bundle.json'
        if (Test-Path -LiteralPath $manifestFile) {
            $identity = Get-Content -LiteralPath $manifestFile -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($identity.name -eq 'cy-charmyee' -and
                (Test-Path -LiteralPath (Join-Path $candidate 'scripts/member-entry.ps1'))) { $shared = $candidate; break }
        }
    }
    if (-not $shared) { throw '找不到同套承意共享运行时，请使用整套安装包修复。' }
    & (Join-Path $shared 'scripts/member-entry.ps1') -MemberRoot $memberRoot @BrainArgs
    exit $LASTEXITCODE
} catch {
    @{status='error';error=$_.Exception.Message} | ConvertTo-Json -Compress
    exit 1
}
