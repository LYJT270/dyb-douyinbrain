function Get-CyFileHash([string]$File) {
    $stream = [IO.File]::OpenRead($File)
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace('-', '').ToLowerInvariant() }
    finally { $stream.Dispose(); $algorithm.Dispose() }
}

function Assert-CySuiteAvailable([string]$SharedRoot) {
    $sentinel = Join-Path (Split-Path -Parent $SharedRoot) '.cy-suite-installing.json'
    if (Test-Path -LiteralPath $sentinel) {
        $transaction = Get-Content -LiteralPath $sentinel -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($env:CY_SUITE_TRANSACTION -ne $transaction.id) {
            throw '整套 Skill 正在安装或需要恢复，请完成安装后继续任务。'
        }
    }
    $manifest = Get-Content -LiteralPath (Join-Path $SharedRoot 'bundle.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($manifest.name -ne 'cy-charmyee') { throw '共享入口身份不一致。' }
    if (-not (Test-Path -LiteralPath (Join-Path $SharedRoot '.cy-suite.json'))) { return $manifest }
    $manifestHash = Get-CyFileHash (Join-Path $SharedRoot 'bundle.json')
    if ((Get-Content -LiteralPath (Join-Path $SharedRoot 'VERSION') -Raw).Trim() -ne $manifest.version) { throw '共享程序版本与清单不一致。' }
    foreach ($member in $manifest.skill_suite.members) {
        $target = Join-Path (Split-Path -Parent $SharedRoot) $member.name
        $marker = Get-Content -LiteralPath (Join-Path $target '.cy-member.json') -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($marker.product -ne 'cy-charmyee' -or $marker.name -ne $member.name -or
            $marker.version -ne $manifest.version -or $marker.manifest_sha256 -ne $manifestHash) { throw ('子 Skill 版本不一致：' + $member.name) }
        $prefix = $member.source + '/'
        foreach ($item in $manifest.file_sha256.PSObject.Properties) {
            if ($item.Name.StartsWith($prefix)) {
                $file = Join-Path $target $item.Name.Substring($prefix.Length)
                if (-not (Test-Path -LiteralPath $file -PathType Leaf) -or (Get-CyFileHash $file) -ne $item.Value) {
                    throw ('子 Skill 文件缺失或已改变，请重新安装整套程序：' + $member.name)
                }
            }
        }
    }
    return $manifest
}
