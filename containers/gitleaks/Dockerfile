# Gitleaks validator: gitleaks binary + Python gRPC shim.
# Multi-stage: copies gitleaks from the official image.
FROM docker.io/zricethezav/gitleaks:latest AS gitleaks-bin

ARG BASE_IMAGE=localhost/apme-base:latest
FROM $BASE_IMAGE

COPY --from=gitleaks-bin /usr/bin/gitleaks /usr/local/bin/gitleaks

ENV APME_GITLEAKS_VALIDATOR_LISTEN=0.0.0.0:50056
EXPOSE 50056

CMD ["apme-gitleaks-validator"]
