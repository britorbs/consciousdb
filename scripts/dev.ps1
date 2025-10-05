param([string]$Port = "8080")
$env:PYTHONPATH = "$PWD"
Write-Host "Starting API on port $Port (USE_MOCK=$env:USE_MOCK)"
uvicorn api.main:app --reload --port $Port
