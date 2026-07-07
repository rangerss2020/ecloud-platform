@echo off
title Seedance Platform 2026-06-30

echo ===========================================
echo   Seedance AI Platform - Auto Start
echo   Build: 2026-06-30
echo ===========================================
echo.

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Install Python 3.8+ first.
    pause
    exit /b 1
)
echo [OK] Python ready

echo.
echo [1/3] Installing dependencies...
pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo [WARN] pip install failed, retrying...
    pip install -r requirements.txt
)
echo [OK] Done

echo.
echo [2/3] Database migration...
python manage.py migrate --noinput
echo [OK] Done

echo.
echo [3/3] Collecting static files...
python manage.py collectstatic --noinput -v 0
echo [OK] Done

echo.
echo ===========================================
echo   Server starting at http://127.0.0.1:8000
echo   Default login: admin / admin123
echo   Press Ctrl+C to stop
echo ===========================================
echo.

python -m waitress --host=0.0.0.0 --port=8000 ecloud_platform.wsgi:application
pause
