# Start the Code Comprehension API Server
# Usage: .\start_api.ps1

Write-Host "🚀 Starting Code Comprehension API..." -ForegroundColor Cyan

# Check if virtual environment exists
if (Test-Path ".\.venv\Scripts\Activate.ps1") {
    Write-Host "📦 Activating virtual environment..." -ForegroundColor Yellow
    .\.venv\Scripts\Activate.ps1
}

# Start the server
Write-Host "🌐 API will be available at: http://localhost:8000" -ForegroundColor Green
Write-Host "📚 Swagger docs at: http://localhost:8000/docs" -ForegroundColor Green
Write-Host ""

python -m uvicorn src.api:app --host 0.0.0.0 --port 8000 --reload
