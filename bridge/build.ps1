$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path $PSScriptRoot -Parent
foreach ($taskRepo in @('discord-botc', 'clocktower-ai')) {
  Push-Location (Join-Path $taskRoot $taskRepo)
  try {
    & node node_modules/typescript/bin/tsc
    if ($LASTEXITCODE -ne 0) { throw "Compilation failed: $taskRepo" }
  } finally { Pop-Location }
}
