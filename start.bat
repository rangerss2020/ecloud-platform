@echo off
chcp 65001 >nul
echo ========================================
echo   ECloud API Platform - Production Start
echo ========================================

cd /d "%~dp0"

echo [1/4] Checking migrations...
python manage.py migrate --noinput
if %errorlevel% neq 0 (
    echo Migration failed!
    pause
    exit /b 1
)

echo [2/4] Checking init data...
python manage.py shell -c "from users.models import User; exit(0 if User.objects.filter(username='admin').exists() else 1)"
if %errorlevel% neq 0 (
    echo Initializing seed data...
    python manage.py initdata
)

echo [3/4] Collecting static files...
python manage.py collectstatic --noinput

echo [4/4] Starting server...
echo.
echo   HTTP:  http://0.0.0.0:8000
echo   Admin: http://0.0.0.0:8000/admin/
echo   API:   http://0.0.0.0:8000/v1
echo.
echo   Press Ctrl+C to stop
echo ========================================

waitress-serve --port=8000 --threads=16 ecloud_platform.wsgi:application
