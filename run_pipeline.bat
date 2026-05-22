@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] .venv\Scripts\python.exe not found.
    echo Create the virtual environment first:
    echo python -m venv .venv
    echo .venv\Scripts\python.exe -m pip install -r requirements.txt
    exit /b 1
)

if not exist ".env" (
    echo [ERROR] .env file not found.
    echo Copy .env.example to .env and fill in the required values.
    exit /b 1
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment.
    exit /b 1
)

if "%LOG_LEVEL%"=="" set "LOG_LEVEL=INFO"

set "PIPELINE_ARGS=%*"
set "UPLOAD_FLAG=--no-upload"
if /i "%~1"=="--upload" (
    set "UPLOAD_FLAG="
    shift
    set "PIPELINE_ARGS=%*"
)

rem Avoid stale local proxy settings such as 127.0.0.1:9 blocking KRX/DART calls.
set "HTTP_PROXY="
set "HTTPS_PROXY="
set "http_proxy="
set "https_proxy="
set "ALL_PROXY="
set "all_proxy="
set "NO_PROXY=data.krx.co.kr,opendart.fss.or.kr,localhost,127.0.0.1"

python -m src.pipeline.runner %PIPELINE_ARGS% %UPLOAD_FLAG%
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo [ERROR] Pipeline failed with exit code %EXIT_CODE%.
    exit /b %EXIT_CODE%
)

echo.
echo [OK] Pipeline completed successfully.
exit /b 0
