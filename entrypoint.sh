#!/usr/bin/env sh
set -e

echo "[entrypoint] Aplicando migrações do banco de dados..."
python manage.py migrate --noinput

echo "[entrypoint] Coletando arquivos estáticos..."
python manage.py collectstatic --noinput

if [ "${SEED_DEMO:-False}" = "True" ]; then
    echo "[entrypoint] Populando catálogo de demonstração da fábrica..."
    python manage.py populate_demo_data
fi

echo "[entrypoint] Iniciando: $*"
exec "$@"
