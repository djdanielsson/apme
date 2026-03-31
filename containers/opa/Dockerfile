# OPA validator: gRPC wrapper over OPA REST API.
# Multi-stage: copies the OPA binary from the official image.
FROM docker.io/openpolicyagent/opa:latest AS opa-bin

ARG BASE_IMAGE=localhost/apme-base:latest
FROM $BASE_IMAGE

COPY --from=opa-bin /opa /usr/local/bin/opa

RUN cp -r /app/src/apme_engine/validators/opa/bundle /bundle \
    && cp /app/containers/opa/entrypoint.sh /entrypoint.sh \
    && chmod +x /entrypoint.sh

ENV APME_OPA_VALIDATOR_LISTEN=0.0.0.0:50054
EXPOSE 50054

ENTRYPOINT ["/entrypoint.sh"]
