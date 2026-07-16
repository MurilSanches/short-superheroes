param(
    [Parameter(Position = 0)]
    [string]$ThemeSeed,

    [switch]$DryRun,
    [string]$BatchId,
    [string]$ImageModel,
    [string]$Python
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$SettingsPath = Join-Path $ProjectRoot "config\settings.example.json"

if (-not $Python) {
    $LocalPython = Join-Path $env:LOCALAPPDATA "Programs\Python\Python310\python.exe"
    if (Test-Path $LocalPython) {
        $Python = $LocalPython
    } else {
        $Python = "python"
    }
}

$env:PYTHONPATH = Join-Path $ProjectRoot "src"

$CliArgs = @(
    "-m", "shorts_superheroes.cli",
    "--settings", $SettingsPath,
    "run-full-batch",
    "--project-root", $ProjectRoot
)

if ($ThemeSeed) {
    $CliArgs += @("--theme-seed", $ThemeSeed)
}

if ($BatchId) {
    $CliArgs += @("--batch-id", $BatchId)
}

if ($ImageModel) {
    $CliArgs += @("--image-model", $ImageModel)
}

if ($DryRun) {
    $CliArgs += "--dry-run"
}

& $Python @CliArgs
exit $LASTEXITCODE
