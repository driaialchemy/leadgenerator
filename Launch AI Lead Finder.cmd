@echo off
cd /d "%~dp0"
rem Stop any old copy of the app on port 8505, then start it fresh and open Chrome.
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8505 " ^| findstr LISTENING') do taskkill /PID %%p /F >nul 2>&1
if "%LEADGEN_LLM_MODE%"=="" set LEADGEN_LLM_MODE=live
if "%LEADGEN_DATA_ROOT%"=="" set "LEADGEN_DATA_ROOT=%LOCALAPPDATA%\AI Lead Finder\sessions\launcher"
start "" cmd /c "timeout /t 8 >nul & start chrome http://localhost:8505"
".venv\Scripts\python.exe" -m streamlit run "src\leadgen\app.py" --server.port 8505 --server.headless true
