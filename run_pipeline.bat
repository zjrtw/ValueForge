@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] .venv\Scripts\python.exe not found.
    echo Run: python -m venv .venv ^&^& .venv\Scripts\python.exe -m pip install -r requirements.txt
    exit /b 1
)

if not exist ".env" (
    echo [ERROR] .env file not found. Copy .env.example to .env and fill in values.
    exit /b 1
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment.
    exit /b 1
)

if "%LOG_LEVEL%"=="" set "LOG_LEVEL=INFO"

set "UPLOAD_FLAG=--no-upload"
set "RUN_TESTS=0"
set "PIPELINE_ARGS="

:arg_loop
if "%~1"=="" goto arg_done
if /i "%~1"=="--upload" (
    set "UPLOAD_FLAG="
    shift
    goto arg_loop
)
if /i "%~1"=="-t" (
    set "RUN_TESTS=1"
    shift
    goto arg_loop
)
set "PIPELINE_ARGS=%PIPELINE_ARGS% %~1"
shift
goto arg_loop
:arg_done

set "DB_PATH_FLAG="
if not "%UPLOAD_FLAG%"=="" (
    echo %PIPELINE_ARGS% | findstr /i "\-\-db-path" >nul || (
        if not exist "data" mkdir data
        set "DB_PATH_FLAG=--db-path data\valueforge_local.db"
    )
)

set "HTTP_PROXY="
set "HTTPS_PROXY="
set "http_proxy="
set "https_proxy="
set "ALL_PROXY="
set "all_proxy="
set "NO_PROXY=data.krx.co.kr,opendart.fss.or.kr,localhost,127.0.0.1"

if "%RUN_TESTS%"=="1" (
    echo.
    echo [LINT] Running ruff...
    ruff check src/
    if errorlevel 1 (
        echo.
        echo [ERROR] Linting failed. Pipeline execution aborted.
        exit /b 1
    )

    echo.
    echo [TYPE] Running mypy...
    mypy src/ --ignore-missing-imports
    if errorlevel 1 (
        echo.
        echo [ERROR] Type check failed. Pipeline execution aborted.
        exit /b 1
    )

    echo.
    echo [TEST] Running pytest...
    pytest tests/ -v
    if errorlevel 1 (
        echo.
        echo [ERROR] Tests failed. Pipeline execution aborted.
        exit /b 1
    )
)

python -m src.pipeline.runner %PIPELINE_ARGS% %UPLOAD_FLAG% %DB_PATH_FLAG%
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo [ERROR] Pipeline failed with exit code %EXIT_CODE%.
    exit /b %EXIT_CODE%
)

echo.
echo [OK] Pipeline completed successfully.
if not "%DB_PATH_FLAG%"=="" (
    echo [DB]  data\valueforge_local.db
)
exit /b 0