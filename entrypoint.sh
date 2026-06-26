#!/bin/bash
set -e

echo "Waiting for MySQL..."
while ! mysqladmin ping -h"$DB_HOST" -u"$DB_USER" -p"$DB_PASSWORD" --silent; do
    sleep 2
done
echo "MySQL is ready"

python manage.py migrate --noinput
python manage.py initdata

echo "Starting ECloud Platform..."
exec waitress-serve --port=8000 --threads=16 ecloud_platform.wsgi:application
