param([ValidateSet('check','start','status','stop','restart-database')][string]$Command = 'start')
$ErrorActionPreference = 'Stop'
$projectDirectory = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
& (Join-Path $projectDirectory 'venv\Scripts\python.exe') -B (Join-Path $PSScriptRoot 'demo.py') $Command
exit $LASTEXITCODE
