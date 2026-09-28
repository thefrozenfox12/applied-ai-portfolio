$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not $env:REVIEW_BASE_URL) { $env:REVIEW_BASE_URL = Read-Host 'Enter your model API base URL' }
if (-not $env:REVIEW_API_KEY) {
    $secureKey = Read-Host 'Enter your provider API key' -AsSecureString
    $env:REVIEW_API_KEY = [System.Net.NetworkCredential]::new('', $secureKey).Password
}
$steps = @(
    @('pipeline.py', 'prepare'),
    @('pipeline.py', 'spotcheck'),
    @('pipeline.py', 'binary'),
    @('pipeline.py', 'three_class'),
    @('experiments.py', 'all'),
    @('emotions.py', 'all'),
    @('analysis.py'),
    @('verify_results.py'),
    @('dashboard.py'),
    @('report.py')
)
foreach ($step in $steps) {
    & python @step
    if ($LASTEXITCODE -ne 0) { throw "Step failed: $step" }
}
Write-Host 'Complete. Open dashboard.html in a browser.'
