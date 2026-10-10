#!/usr/bin/env sh
set -e

echo "[entrypoint] Aplicando migrações do banco de dados..."
python manage.py migrate --noinput

echo "[entrypoint] Coletando arquivos estáticos..."
python manage.py collectstatic --noinput

echo "[entrypoint] Iniciando: $*"
exec "$@"
