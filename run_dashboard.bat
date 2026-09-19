@echo off
title BDD Agent v2 - Autonomous AI QA Testing Platform
cls
echo =====================================================================
echo  BDD Agent v2: Autonomous AI QA Testing Platform
echo  Powered by FastMCP, Python Playwright, and Gherkin BDD
echo =====================================================================
echo.

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python was not found in your PATH!
    echo Please install Python 3.10+ from https://www.python.org/
    pause
    exit /b 1
)

echo [*] Starting BDD Agent v2 Dashboard on http://127.0.0.1:7861 ...
echo [*] Press Ctrl+C in this window at any time to stop the server.
echo.

start "" "http://127.0.0.1:7861/"
python app.py

pause
