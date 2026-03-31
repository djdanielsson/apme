# Ansible validator: async gRPC server, read-only consumer of session venvs.
# UV cache is pre-warmed at build time so venv creation by Primary is near-instant.
# Sessions volume mounted read-only from the Primary orchestrator.
ARG BASE_IMAGE=localhost/apme-base:latest
FROM $BASE_IMAGE

# Pre-warm UV cache for supported ansible-core versions
ENV UV_CACHE_DIR=/opt/uv-cache
RUN chmod +x containers/ansible/prebuild-venvs.sh \
    && containers/ansible/prebuild-venvs.sh

ENV APME_ANSIBLE_VALIDATOR_LISTEN=0.0.0.0:50053
ENV APME_COLLECTION_CACHE=/sessions
EXPOSE 50053

CMD ["apme-ansible-validator"]
