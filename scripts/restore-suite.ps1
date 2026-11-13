param([Parameter(Mandatory=$true)][string]$TransactionPath,
      [Parameter(Mandatory=$true)][string]$SkillsRoot)
$ErrorActionPreference = 'Stop'
try {
    . (Join-Path $PSScriptRoot 'suite-install.ps1')
    $transaction = Get-Content -LiteralPath $TransactionPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ([IO.Path]::GetFullPath($transaction.skills_root) -ne [IO.Path]::GetFullPath($SkillsRoot) -or
        [IO.Path]::GetFullPath($transaction.journal) -ne [IO.Path]::GetFullPath($TransactionPath)) { throw '恢复事务与指定安装位置不一致。' }
    $lock = [IO.File]::Open((Join-Path (Split-Path -Parent $TransactionPath) 'install.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
    try {
        $restored = Undo-CySuiteInstall $transaction -IncludeCommitted
        @{status=$restored.status;entries=$restored.entries} | ConvertTo-Json -Depth 8
    } finally { $lock.Dispose() }
} catch {
    @{status='error';error=$_.Exception.Message} | ConvertTo-Json -Compress
    exit 1
}
