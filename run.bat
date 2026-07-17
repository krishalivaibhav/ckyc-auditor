@echo off
REM ============================================================================
REM  TechMKYC - run the ENTIRE agent backend on Windows (mirror of run_backend.sh)
REM
REM    news agent (:8002)  --POST /signals/ingest-->  pipeline service (:8001)
REM    sanctions monitor   --POST /api/ingest------>  (ambiguity ER + investigation
REM                                                    + SAR draft + SQLite sink)
REM                                                          |  ckyc.db
REM    Flutter dashboard  <--:8787--  read-API adapter  <----+
REM
REM  ONE-TIME SETUP (each agent keeps its own venv):
REM    python -m venv investigation_agent\.venv
REM    investigation_agent\.venv\Scripts\pip install fastapi "uvicorn[standard]" ^
REM        pydantic jellyfish python-dotenv httpx anthropic pytest
REM    python -m venv news_agent\.venv
REM    news_agent\.venv\Scripts\pip install -r news_agent\signals\requirements.txt
REM
REM  THEN:      run.bat                 (double-click, or run in a terminal)
REM  DASHBOARD: flutter run -d chrome   (in another terminal)
REM
REM  Each long-running service opens in its OWN window. Keep the "Pipeline"
REM  window visible - it narrates the LIVE/TEST demo. Close the three server
REM  windows to stop the backend.
REM ============================================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"

REM ---- ports / key (override by setting them in the environment first) -------
if not defined PIPE_PORT       set "PIPE_PORT=8001"
if not defined NEWS_PORT       set "NEWS_PORT=8002"
if not defined READ_PORT       set "READ_PORT=8787"
if not defined SIGNALS_API_KEY set "SIGNALS_API_KEY=signals-dev-key-change-in-production"

set "PIPE_PY=investigation_agent\.venv\Scripts\python.exe"
set "NEWS_PY=news_agent\.venv\Scripts\python.exe"

if not exist "%PIPE_PY%" (
    echo missing investigation_agent\.venv  -  see ONE-TIME SETUP in this script
    exit /b 1
)
if not exist "%NEWS_PY%" (
    echo missing news_agent\.venv  -  see ONE-TIME SETUP in this script
    exit /b 1
)

REM ---- fresh demo: wipe the news-side state so signals re-emit ---------------
del /q "news_agent\signals\signals.db" 2>nul
del /q "news_agent\signals_log.jsonl"  2>nul

REM ===========================================================================
echo [1/5] pipeline service (ambiguity + investigation) on :%PIPE_PORT%
start "TechMKYC Pipeline :%PIPE_PORT%" cmd /k "cd /d investigation_agent && .venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port %PIPE_PORT%"
call :wait_for "http://127.0.0.1:%PIPE_PORT%/health" "pipeline"

REM ===========================================================================
echo [2/5] news agent on :%NEWS_PORT% (mock news, shared dataset)
REM Point the emitter at THIS pipeline (child window inherits these env vars).
set "CORE_API_URL=http://127.0.0.1:%PIPE_PORT%/signals/ingest"
start "TechMKYC News :%NEWS_PORT%" cmd /k "cd /d news_agent && .venv\Scripts\python.exe -m uvicorn signals.main:app --host 127.0.0.1 --port %NEWS_PORT%"
call :wait_for "http://127.0.0.1:%NEWS_PORT%/signals/health" "news agent"

REM ===========================================================================
echo [3/5] sanctions monitor -^> /api/ingest (one pass over the delta stream)
pushd Sanctions_agent
..\investigation_agent\.venv\Scripts\python.exe -m watchlist.monitor --base-url "http://127.0.0.1:%PIPE_PORT%"
popd

REM ===========================================================================
echo [4/5] news scan -^> emit -^> /signals/ingest
curl -s -X POST -H "X-API-Key: %SIGNALS_API_KEY%" "http://127.0.0.1:%NEWS_PORT%/signals/scan/trigger" >nul 2>&1
echo       scanner runs in a thread; giving the emit cycle time to finish...
timeout /t 12 /nobreak >nul

REM ===========================================================================
echo [5/5] read-API adapter on :%READ_PORT% (what the Flutter dashboard reads)
REM Pin the PIPELINE's sink so a stale root ckyc.db never wins. Reuse the pipeline
REM venv's python (the read-API is stdlib-only, any Python 3 works).
set "CKYC_DB=%CD%\investigation_agent\ckyc.db"
start "TechMKYC Read-API :%READ_PORT%" cmd /k "%PIPE_PY% api\server.py --port %READ_PORT%"
call :wait_for "http://127.0.0.1:%READ_PORT%/api/health" "read-api"

REM ===========================================================================
echo.
echo Backend is live:
echo   pipeline   http://127.0.0.1:%PIPE_PORT%/docs
echo   news agent http://127.0.0.1:%NEWS_PORT%/docs
echo   dashboard  http://127.0.0.1:%READ_PORT%/api/alerts
echo.
echo Now run the dashboard:  flutter run -d chrome
echo.
echo Judges' demo: toggle LIVE -^> TEST on the dashboard. The "Pipeline" window
echo narrates the scripted Vijay Mallya scenario; the "Time skip +15 months"
echo button on the case page runs phase 2 (more articles + the SEBI sanction
echo -^> CRITICAL + SAR).
echo.
echo Close the three server windows (Pipeline / News / Read-API) to stop the backend.
echo.
pause
exit /b 0

REM ===========================================================================
REM  :wait_for  url  label   - poll until the health URL answers (needs curl)
REM ===========================================================================
:wait_for
set "_url=%~1"
set "_label=%~2"
for /l %%i in (1,1,40) do (
    curl -sf "!_url!" >nul 2>&1 && ( echo   !_label! is up. & exit /b 0 )
    timeout /t 1 /nobreak >nul
)
echo   !_label! did NOT come up - check its window / logs
exit /b 1
