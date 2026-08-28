<#
.SYNOPSIS
  并行运行 normal、no-rag、no-rerank、single-model 四个完全隔离的 Docker Compose 评测栈。

.EXAMPLE
  .\scripts\run-evaluation-matrix.ps1
  .\scripts\run-evaluation-matrix.ps1 -Experiments normal,no-rag -Profiles '1-3-5' -TargetRound 2
#>
[CmdletBinding()]
param(
    [string[]]$Experiments = @('normal', 'no-rag', 'no-rerank', 'single-model'),
    [string]$Profiles,
    [int]$TargetRound,
    [switch]$KeepStacks
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$composeFile = Join-Path $ProjectRoot 'docker-compose.evaluation.yml'
if (-not (Test-Path $composeFile)) {
    throw "Missing compose file: $composeFile"
}

# 同名外部卷让所有栈复用只读模型，不共享 MySQL、artifacts 或网络。
$modelVolume = 'patent-tutor-evaluation-models'
$volumeExists = docker volume ls --format '{{.Name}}' | Where-Object { $_ -eq $modelVolume }
if (-not $volumeExists) {
    Write-Host "Creating shared model volume: $modelVolume"
    docker volume create $modelVolume | Out-Null
}

$jobs = @()
$jobMetadata = @{}
foreach ($experiment in $Experiments) {
    $envFile = Join-Path $ProjectRoot "docker/evaluation/$experiment.env"
    if (-not (Test-Path $envFile)) {
        throw "Unknown experiment '$experiment': $envFile does not exist"
    }

    # CLI 环境变量优先级高于 env 文件，可临时缩小样本/轮次，无须编辑基线定义。
    $prefix = "evaluation-$experiment"
    $command = @(
        'compose', '-p', $prefix,
        '--env-file', '.env', '--env-file', "docker/evaluation/$experiment.env",
        '-f', 'docker-compose.evaluation.yml',
        'up', '--build', '--abort-on-container-exit', '--exit-code-from', 'evaluator', 'evaluator'
    )
    $outputPath = "artifacts/evaluation/$experiment/compose.log"
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $outputPath) | Out-Null

    Write-Host "Starting $experiment ..."
    $job = Start-Job -Name $experiment -ScriptBlock {
        param($ProjectRoot, $Command, $OutputPath, $Profiles, $TargetRound, $EnvFile)
        Set-Location $ProjectRoot
        # 组 env 文件是评测条件的唯一权威来源：解析后显式注入进程环境
        # （优先级高于 --env-file），覆盖终端/用户环境里残留的同名导出。
        Get-Content $EnvFile | ForEach-Object {
            if ($_ -match '^([A-Za-z_][A-Za-z0-9_]*)=(.*)$') {
                [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2], 'Process')
            }
        }
        if ($Profiles) { $env:EVAL_PROFILES = $Profiles }
        if ($TargetRound) { $env:EVAL_TARGET_ROUND = "$TargetRound" }
        # 评测栈强制关闭结构化课件/PPT 节点（进程环境优先级高于 --env-file，
        # 避免终端导出过 true 时 slide_deck/generate_pptx 意外运行）。
        $env:PATENT_TUTOR_SLIDE_DECK_ENABLED = 'false'
        $env:PATENT_TUTOR_PPTX_ENABLED = 'false'
        & docker @Command 2>&1 | Tee-Object -FilePath $OutputPath
        return $LASTEXITCODE
    } -ArgumentList $ProjectRoot, $command, $outputPath, $Profiles, $TargetRound, $envFile
    $jobs += $job
    $jobMetadata[$job.Id] = @{ Experiment = $experiment; OutputPath = $outputPath }
}

$failed = @()
foreach ($job in $jobs) {
    Wait-Job $job | Out-Null
    $result = Receive-Job $job
    $exitCode = $result | Select-Object -Last 1
    $metadata = $jobMetadata[$job.Id]
    if ($job.State -ne 'Completed' -or $job.ChildJobs[0].Error.Count -gt 0 -or $exitCode -ne 0) {
        $failed += $metadata.Experiment
        Write-Error "Failed $($metadata.Experiment); see $($metadata.OutputPath)"
        continue
    }
    Write-Host "Finished $($metadata.Experiment); see $($metadata.OutputPath)"
}
Remove-Job $jobs -Force

if (-not $KeepStacks) {
    foreach ($experiment in $Experiments) {
        Write-Host "Cleaning isolated stack evaluation-$experiment (preserving named MySQL volume for inspection) ..."
        docker compose -p "evaluation-$experiment" --env-file .env --env-file "docker/evaluation/$experiment.env" -f docker-compose.evaluation.yml down --remove-orphans
    }
}

if ($failed.Count -gt 0) {
    throw "Jobs did not complete cleanly: $($failed -join ', ')"
}
Write-Host 'All experiment containers completed. Results: artifacts/evaluation/<experiment>/results/'
