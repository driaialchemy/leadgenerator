Set-Location $PSScriptRoot
if (-not $env:LEADGEN_LLM_MODE) {
    $env:LEADGEN_LLM_MODE = "live"
}
if (-not $env:LEADGEN_DATA_ROOT) {
    $sessionStamp = Get-Date -Format "yyyyMMddTHHmmssfff"
    $env:LEADGEN_DATA_ROOT = Join-Path $env:LOCALAPPDATA "AI Lead Finder\sessions\$sessionStamp"
}
& "$PSScriptRoot\.venv\Scripts\python.exe" -m streamlit run "$PSScriptRoot\src\leadgen\app.py"
