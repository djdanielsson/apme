# CLI: calls Primary over gRPC for check/remediate, runs format locally.
# Mount project at /workspace; set APME_PRIMARY_ADDRESS to primary service.
ARG BASE_IMAGE=localhost/apme-base:latest
FROM $BASE_IMAGE

ENV APME_PRIMARY_ADDRESS=primary:50051
WORKDIR /workspace

ENTRYPOINT ["apme"]
CMD ["check", "."]
