@echo off
setlocal
set "ROOT=%~dp0"

echo Starting PitSense AI...

if not exist "%ROOT%backend\.env" (
  echo WARNING: backend\.env was not found. Copy backend\.env.example to backend\.env first.
)

start "PitSense Backend" powershell -NoExit -ExecutionPolicy Bypass -Command "Set-Location -LiteralPath '%ROOT%backend'; if (Test-Path '.venv311\Scripts\python.exe') { & '.venv311\Scripts\python.exe' -m uvicorn app.main:app --reload --port 8000 } else { Write-Host 'Python 3.11 backend environment missing. Run: powershell -ExecutionPolicy Bypass -File .\setup-windows.ps1' -ForegroundColor Red }"

start "PitSense Frontend" powershell -NoExit -ExecutionPolicy Bypass -Command "Set-Location -LiteralPath '%ROOT%frontend'; if (!(Test-Path 'node_modules')) { npm install }; npm run dev"

timeout /t 3 /nobreak >nul
start "" "http://localhost:3000"

echo Backend: http://localhost:8000
echo Frontend: http://localhost:3000
echo API docs: http://localhost:8000/docs
endlocal
