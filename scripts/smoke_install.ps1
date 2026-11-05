param([Parameter(Mandatory=$true)][string]$PythonExecutable, [string]$SandboxDirectory)
$ErrorActionPreference = 'Stop'
$env:DYB_UPDATE_CHECK = '0'
$OutputEncoding = [Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$source = Split-Path -Parent $PSScriptRoot
$sandbox = if ($SandboxDirectory) { [IO.Path]::GetFullPath($SandboxDirectory) } else { Join-Path ([IO.Path]::GetTempPath()) ('dyb-smoke-' + [Guid]::NewGuid().ToString('N')) }
$state = Join-Path $sandbox 'state'
$data = Join-Path $sandbox 'data with spaces'
$skills = Join-Path $sandbox 'skills'
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $source 'scripts\install.ps1') -Agent shared -SkillsRoot $skills -StateDirectory $state -DataDirectory $data -PythonExecutable $PythonExecutable -NoApiWindow
if ($LASTEXITCODE -ne 0) { throw 'Full installation failed; isolated evidence remains at ' + $sandbox }
$result = Get-Content -LiteralPath (Join-Path $state 'install-result.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if ($result.status -ne 'awaiting_api' -or -not $result.local_entry_verified -or $result.live_asr_requests -ne 0) {
    throw 'Installation did not reach the expected local-ready / no-API state.'
}
$env:DYB_STATE_DIR = $state
$entry = $result.entrypoint
$doctorText = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $entry doctor
if ($LASTEXITCODE -ne 0) { throw 'Installed entrypoint doctor failed.' }
$doctor = ($doctorText -join "`n") | ConvertFrom-Json
if ($doctor.status -ne 'environment_ready') { throw 'Installed environment is incomplete.' }
$sample = Join-Path $sandbox 'sample.txt'
[IO.File]::WriteAllText($sample, 'A short local transcript. Keep this source unchanged.', [Text.UTF8Encoding]::new($false))
$planText = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $entry plan-text $sample
if ($LASTEXITCODE -ne 0) { throw 'Text-only task could not be started without API credentials.' }
$task = ($planText -join "`n") | ConvertFrom-Json
if ($task.status -ne 'needs_intent') { throw 'Unexpected text task state.' }
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $entry confirm $task.id --purpose transcribe --evidence 'Review and deliver this isolated test transcript.' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Text task purpose registration failed.' }
$readyText = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $entry run $task.id
if ($LASTEXITCODE -ne 0) { throw 'Text import failed.' }
$ready = ($readyText -join "`n") | ConvertFrom-Json
if ($ready.status -ne 'awaiting_review') { throw 'Text import did not reach review.' }
$review = Join-Path $result.workspace ('runs\' + $task.id + '\review.txt')
[IO.File]::WriteAllText($review, 'A short local transcript. Keep this source unchanged.', [Text.UTF8Encoding]::new($false))
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $entry register-review $task.id --file $review | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Review registration failed.' }
$deliveredText = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $entry deliver $task.id
if ($LASTEXITCODE -ne 0) { throw 'Text delivery failed.' }
$delivered = ($deliveredText -join "`n") | ConvertFrom-Json
if ($delivered.status -ne 'completed') { throw 'Text delivery did not complete.' }
$output = Join-Path $delivered.workspace $delivered.delivery.file
if (-not (Test-Path -LiteralPath $output)) { throw 'Delivery file is missing.' }
if (Get-ChildItem -LiteralPath $sandbox -Filter '*.dpapi' -File -Recurse) { throw 'Unexpected credentials were created.' }
[ordered]@{status='passed';sandbox=$sandbox;local_entry_verified=$true;text_delivery_verified=$true;live_asr_requests=0;output=$output} | ConvertTo-Json
