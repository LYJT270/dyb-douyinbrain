param([Parameter(Mandatory=$true)][string]$MemberRoot,
      [Parameter(ValueFromRemainingArguments=$true)][string[]]$BrainArgs)
$ErrorActionPreference = 'Stop'
try {
    . (Join-Path $PSScriptRoot 'paths.ps1')
    . (Join-Path $PSScriptRoot 'suite-guard.ps1')
    $sharedRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
    $MemberRoot = [IO.Path]::GetFullPath($MemberRoot)
    $name = Split-Path -Leaf $MemberRoot
    $manifest = Assert-CySuiteAvailable $sharedRoot
    $member = @($manifest.skill_suite.members | Where-Object { $_.name -eq $name })
    if ($member.Count -ne 1) { throw '子 Skill 不属于此套件。' }
    $sourcePath = [IO.Path]::GetFullPath((Join-Path $sharedRoot $member[0].source))
    $installedPath = [IO.Path]::GetFullPath((Join-Path (Split-Path -Parent $sharedRoot) $name))
    $layout = if ($MemberRoot -eq $sourcePath) { 'source' } elseif ($MemberRoot -eq $installedPath) { 'installed' } else { throw '子 Skill 与共享程序位置不匹配。' }
    $prefix = $member[0].source + '/'
    foreach ($item in $manifest.file_sha256.PSObject.Properties) {
        if ($item.Name.StartsWith($prefix)) {
            $file = Join-Path $MemberRoot $item.Name.Substring($prefix.Length)
            if (-not (Test-Path -LiteralPath $file -PathType Leaf) -or (Get-CyFileHash $file) -ne $item.Value) { throw '子 Skill 文件与整套版本不一致，请重新安装。' }
        }
    }
    if ($BrainArgs.Count -eq 1 -and $BrainArgs[0] -eq 'guide') {
        $references = @{}
        foreach ($topic in @('suite','onboarding','runtime','content','creator','knowledge','work','continuation','personal-vault')) {
            $references[$topic] = Join-Path $sharedRoot ('references/' + $topic + '.md')
        }
        $result = @{status='ready';skill=$name;version=$manifest.version;shared_root=$sharedRoot;
                    entrypoint=(Join-Path $sharedRoot 'scripts/invoke.ps1');references=$references;layout=$layout}
        $settingsPath = Join-Path (Get-CyStateRoot) 'settings.json'
        if (Test-Path -LiteralPath $settingsPath) { $result.workspace = (Get-Content -LiteralPath $settingsPath -Raw -Encoding UTF8 | ConvertFrom-Json).workspace }
        $result | ConvertTo-Json -Depth 5
        exit 0
    }
    & (Join-Path $PSScriptRoot 'invoke.ps1') @BrainArgs
    exit $LASTEXITCODE
} catch {
    @{status='error';error=$_.Exception.Message} | ConvertTo-Json -Compress
    exit 1
}
