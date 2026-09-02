# Refresh Fund Finder data (tables AND detail) and push to deploy.
#
# Run this from your own machine — Yahoo's composition (quoteSummary) endpoint
# is blocked from datacenter IPs, so this is the only place the holdings /
# sectors / ratios snapshot can be rebuilt. Pushing triggers a Render deploy.
#
#   Run once:   powershell -ExecutionPolicy Bypass -File scripts\refresh-data.ps1
#
#   Schedule weekly (Mondays 9am) via Task Scheduler — run once in a terminal:
#     schtasks /create /tn "BTN ETF data refresh" /sc weekly /d MON /st 09:00 ^
#       /tr "powershell -ExecutionPolicy Bypass -File \"%CD%\scripts\refresh-data.ps1\""
#   (run that from the ETF Tool folder so %CD% resolves correctly)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }

Write-Host "Rebuilding fund data..."
& $python build_universe.py --refresh

git add static/data/fund_tables.json static/data/fund_details.json
git diff --staged --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Host "No data changes."
    exit 0
}
git commit -m "Refresh fund data"
git push
Write-Host "Pushed refreshed data — Render will redeploy."
