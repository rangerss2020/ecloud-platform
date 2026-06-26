#!/bin/bash
set -e

echo "Waiting for MySQL..."
until python -c "import MySQLdb; MySQLdb.connect(host='$DB_HOST', user='$DB_USER', password='$DB_PASSWORD', db='$DB_NAME')" 2>/dev/null; do
    sleep 2
done
echo "MySQL ready"

python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py initdata

echo "Starting ECloud..."
exec python manage.py runserver 0.0.0.0:8000
