FROM nginx:1.27-alpine

# openssl: geração do certificado self-signed de bootstrap
# gettext: fornece o comando envsubst para processar o template
RUN apk add --no-cache openssl gettext

# Template processado pelo script de bootstrap em /docker-entrypoint.d
COPY default.conf /etc/nginx/default.conf.template
COPY docker-entrypoint.sh /docker-entrypoint.d/10-bcmodas-bootstrap.sh
RUN chmod +x /docker-entrypoint.d/10-bcmodas-bootstrap.sh

EXPOSE 80 443
