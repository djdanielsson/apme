# Galaxy proxy: PEP 503 bridge from Ansible Galaxy to pip/uv.
# Serves collections as Python wheels on demand; caches internally.
# Mount cache volume at /cache for persistence across restarts.
ARG BASE_IMAGE=localhost/apme-base:latest
FROM $BASE_IMAGE

EXPOSE 8765

VOLUME /cache

ENTRYPOINT ["galaxy-proxy"]
CMD ["--host", "0.0.0.0", "--port", "8765", "--cache-dir", "/cache"]
