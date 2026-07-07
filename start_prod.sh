#!/bin/bash
set -e

echo "==========================================="
echo "  Seedance AI Platform - Production"
echo "  Build: 2026-06-30"
echo "==========================================="

# 默认环境变量
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-ecloud_platform.settings_prod}"
export DJANGO_DEBUG="${DJANGO_DEBUG:-false}"
export ALLOWED_HOSTS="${ALLOWED_HOSTS:-*}"

echo "[OK] Settings: ${DJANGO_SETTINGS_MODULE}"

# 安装依赖
echo "[1/4] Installing dependencies..."
pip install -r requirements.txt -q
echo "[OK] Done"

# 迁移
echo "[2/4] Running migrations..."
python manage.py migrate --noinput
echo "[OK] Done"

# 初始化
echo "[noop] Seeding data..."
# initdata skipped, run manually: python manage.py initdata
echo "[OK] Done"

# 静态文件
echo "[3/4] Collecting static files..."
python manage.py collectstatic --noinput -v 0
echo "[OK] Done"

echo ""
echo "Starting server on 0.0.0.0:8000 ..."
echo "Default: admin / admin123"
echo ""

gunicorn ecloud_platform.wsgi:application --bind 0.0.0.0:8000 --workers 4 --timeout 120
