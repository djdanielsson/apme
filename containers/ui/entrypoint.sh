#!/bin/sh
# Extract the nameserver from /etc/resolv.conf and inject it into the nginx
# config template. Works on both Docker (127.0.0.11) and Podman (aardvark-dns
# at the network gateway IP).
DNS_RESOLVER=$(awk '/^nameserver/{print $2; exit}' /etc/resolv.conf)
DNS_RESOLVER="${DNS_RESOLVER:-127.0.0.11}"
APME_API_BACKEND="${APME_API_BACKEND:-http://127.0.0.1:8080}"

export DNS_RESOLVER APME_API_BACKEND
envsubst '${DNS_RESOLVER} ${APME_API_BACKEND}' \
  < /etc/nginx/conf.d/default.conf.template \
  > /etc/nginx/conf.d/default.conf

exec nginx -g 'daemon off;'
