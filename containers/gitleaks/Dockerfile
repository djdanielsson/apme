# Gitleaks validator: gitleaks binary + Python gRPC shim.
# Multi-stage: copies gitleaks from the official image.
ARG BASE_IMAGE=localhost/apme-base:latest
FROM docker.io/zricethezav/gitleaks:latest AS gitleaks-bin
FROM $BASE_IMAGE

COPY --from=gitleaks-bin /usr/bin/gitleaks /usr/local/bin/gitleaks

ENV APME_GITLEAKS_VALIDATOR_LISTEN=0.0.0.0:50056
EXPOSE 50056

CMD ["apme-gitleaks-validator"]
