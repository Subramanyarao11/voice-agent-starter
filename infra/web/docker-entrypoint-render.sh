#!/bin/sh
set -eu

# Render injects PORT. Local Compose keeps the default listen 80 from the conf.
listen_port="${PORT:-80}"
sed -i "s/listen 80;/listen ${listen_port};/" /etc/nginx/conf.d/default.conf

exec nginx -g "daemon off;"
