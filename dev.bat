@echo off
chcp 65001 >nul
echo ========================================
echo   ECloud Platform - Development Server
echo ========================================

cd /d "%~dp0"

echo [1/2] Checking migrations...
python manage.py migrate --noinput

echo [2/2] Starting development server...
echo.
echo   HTTP: http://127.0.0.1:8000
echo.
echo   Press Ctrl+C to stop
echo ========================================

python manage.py runserver 0.0.0.0:8000
