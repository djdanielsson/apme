# Gateway: gRPC Reporting receiver + FastAPI REST API.
# Persists scan/fix events to SQLite (ADR-020 / ADR-029).
# Project operations require git for on-demand cloning (ADR-037).
# Mount /data for SQLite persistence across restarts.
ARG BASE_IMAGE=localhost/apme-base:latest
FROM $BASE_IMAGE

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

ENV APME_DB_PATH=/data/apme.db
ENV APME_GATEWAY_GRPC_LISTEN=0.0.0.0:50060
ENV APME_GATEWAY_HTTP_HOST=0.0.0.0
ENV APME_GATEWAY_HTTP_PORT=8080
EXPOSE 50060 8080

VOLUME /data

CMD ["apme-gateway"]
