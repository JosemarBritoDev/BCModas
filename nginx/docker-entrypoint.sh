#!/bin/sh
set -e

DOMAIN="${DOMAIN:-localhost}"
CERT_DIR="/etc/nginx/certs"
LE_DIR="/etc/letsencrypt/live/${DOMAIN}"

mkdir -p "${CERT_DIR}"

# Usa o certificado real do Let's Encrypt quando existir; caso contrário gera
# um self-signed para que o Nginx suba já com TLS habilitado (bootstrap).
if [ -f "${LE_DIR}/fullchain.pem" ]; then
    echo "[nginx] Usando certificado Let's Encrypt para ${DOMAIN}"
    cp -L "${LE_DIR}/fullchain.pem" "${CERT_DIR}/${DOMAIN}.crt"
    cp -L "${LE_DIR}/privkey.pem"   "${CERT_DIR}/${DOMAIN}.key"
elif [ ! -f "${CERT_DIR}/${DOMAIN}.crt" ]; then
    echo "[nginx] Certificado real ausente — gerando self-signed para ${DOMAIN}"
    openssl req -x509 -nodes -newkey rsa:2048 -days 90 \
        -keyout "${CERT_DIR}/${DOMAIN}.key" \
        -out "${CERT_DIR}/${DOMAIN}.crt" \
        -subj "/CN=${DOMAIN}" >/dev/null 2>&1
fi

echo "[nginx] Gerando configuração (DOMAIN=${DOMAIN})"
envsubst '${DOMAIN}' < /etc/nginx/default.conf.template > /etc/nginx/conf.d/default.conf
