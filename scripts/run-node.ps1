[CmdletBinding()]
param(
    [ValidateSet("route", "diagnosis_feedback", "planner", "retrieve_context", "chat_answer", "expert_a", "expert_b", "judge", "slide_deck")]
    [string]$Node,
    [string]$Phase,
    [string]$Fixture = "backend\scripts\node_fixtures.json",
    [string]$ArtifactRoot = "artifacts\node-runs",
    [string]$SessionId,
    [switch]$Json
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot
$env:PYTHONUTF8 = "1"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv command was not found. Install uv and run 'uv sync' first."
}

$runnerArgs = @(
    "run", "python", "backend/scripts/run_node.py",
    "--fixture", $Fixture,
    "--artifact-root", $ArtifactRoot
)
if ($Node) { $runnerArgs += @("--node", $Node) }
if ($Phase) { $runnerArgs += @("--phase", $Phase) }
if ($SessionId) { $runnerArgs += @("--session-id", $SessionId) }
if ($Json) { $runnerArgs += "--json" }

Write-Host "[node-run] fixture: $Fixture"
Write-Host "[node-run] artifacts: $ArtifactRoot"
if ($Node) { Write-Host "[node-run] node: $Node" }
if ($Phase) { Write-Host "[node-run] phase: $Phase" }
Write-Host "[node-run] database: disabled (standalone node mode)"

& uv @runnerArgs
$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) {
    Write-Error "Node run failed with exit code $exitCode."
    exit $exitCode
}
