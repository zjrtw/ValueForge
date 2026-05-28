@echo off
REM Sync ValueForge DB from R2 to local

setlocal enabledelayedexpansion

echo.
echo ================================
echo Sync R2 DB to Local
echo ================================
echo.

set PROJECT_DIR=%~dp0
cd /d %PROJECT_DIR%

set LOCAL_DB=%PROJECT_DIR%\.local\valueforge_latest.db
set TEMP_DB=%TEMP%\valueforge_r2_sync.db

if not exist "%PROJECT_DIR%\.local" (
    mkdir "%PROJECT_DIR%\.local"
    echo [Create] .local directory
)

echo [Download] Downloading from R2...
python -c "import sys, os; from pathlib import Path; sys.path.insert(0, os.environ['PROJECT_DIR']); from src.storage.downloader import download_latest_db; p=Path(os.environ['TEMP_DB']); p.unlink(missing_ok=True); download_latest_db(dest=p); print('OK - Downloaded:', p)"

if errorlevel 1 (
    echo [ERROR] Download failed
    goto :error
)

echo.
echo [Verify] Checking database...
python -c "import sqlite3, os; conn = sqlite3.connect(os.environ['TEMP_DB']); c = conn.cursor(); print('Scores:', c.execute('SELECT COUNT(*) FROM scores').fetchone()[0]); print('Rankings:', c.execute('SELECT COUNT(*) FROM rankings').fetchone()[0]); print('Latest:', c.execute('SELECT MAX(run_date) FROM pipeline_runs WHERE status=?', ('SUCCESS',)).fetchone()[0]); conn.close()"

if errorlevel 1 (
    echo [ERROR] Verify failed
    goto :error
)

echo.
echo [Copy] Copying to local DB...

if exist "%LOCAL_DB%" (
    for /f "tokens=2-4 delims=/ " %%a in ('date /t') do (set mydate=%%c%%a%%b)
    for /f "tokens=1-2 delims=/:" %%a in ('time /t') do (set mytime=%%a%%b)
    set BACKUP_FILE=%LOCAL_DB%.backup.!mydate!_!mytime!
    copy "%LOCAL_DB%" "!BACKUP_FILE!" >nul
    echo [Backup] %LOCAL_DB%
)

copy "%TEMP_DB%" "%LOCAL_DB%" >nul
if errorlevel 1 (
    echo [ERROR] Copy failed
    goto :error
)

echo [OK] Local DB updated: %LOCAL_DB%

echo.
echo [Clean] Removing temp files...
if exist "%TEMP_DB%" del "%TEMP_DB%"

echo.
echo ================================
echo OK - Sync complete!
echo ================================
echo.
echo Next: streamlit run src/ui/app.py
echo.

endlocal
goto :end

:error
echo.
echo ================================
echo ERROR - Sync failed
echo ================================
echo.
endlocal
exit /b 1

:end
