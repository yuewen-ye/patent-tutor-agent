[CmdletBinding()]
param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$LearnerId = "yuewen-ye99",
    [ValidateSet("correct", "incorrect")]
    [string]$AnswerMode = "correct",
    [ValidateRange(1, 20)]
    [int]$MaxExercises = 3,
    [ValidateSet("interactive", "off")]
    [string]$CatMode = "interactive",
    [string]$EducationBackground = "其他",
    [ValidateRange(0, 40)]
    [int]$CatMaxAnswers = 0,
    [ValidateRange(1, 86400)]
    [int]$WorkflowTimeout = 3600
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot
$env:PYTHONUTF8 = "1"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv command was not found. Install uv and run 'uv sync' first."
}

$safeLearnerId = $LearnerId -replace '[^A-Za-z0-9_-]', '-'
$outputPath = Join-Path $repoRoot "artifacts\api-journey-$safeLearnerId.json"
$journeyArgs = @(
    "run",
    "python",
    "backend/scripts/run_api_journey.py",
    "--base-url", $BaseUrl,
    "--learner-id", $LearnerId,
    "--answer-mode", $AnswerMode,
    "--max-exercises", $MaxExercises,
    "--cat-mode", $CatMode,
    "--education-background", $EducationBackground,
    "--cat-max-answers", $CatMaxAnswers,
    "--workflow-timeout", $WorkflowTimeout,
    "--output-json", $outputPath
)

Write-Host "[api-journey] FastAPI: $BaseUrl"
Write-Host "[api-journey] learner_id: $LearnerId"
Write-Host "[api-journey] answer_mode: $AnswerMode"
Write-Host "[api-journey] cat_mode: $CatMode"

& uv @journeyArgs
$journeyExitCode = $LASTEXITCODE
if ($journeyExitCode -ne 0) {
    Write-Error "API journey failed with exit code $journeyExitCode."
    exit $journeyExitCode
}

Write-Host "[api-journey] 完成。结果文件：$outputPath"
