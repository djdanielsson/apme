# Abbenay AI daemon: gRPC-based LLM gateway for AI-assisted remediation.
# Downloads the pre-built binary from the GitHub release. Requires
# containers/abbenay/.env with LLM provider API keys at runtime.
FROM node:22-alpine

ARG ABBENAY_VERSION=v2026.3.6-alpha
ARG ABBENAY_SHA256=e28cae23a3c4eac3d389b460268a76527ca27050fe5488bdd594e62bb040c2e2

WORKDIR /opt/abbenay

# Download, verify, and extract the release binary + proto files.
RUN set -eux; \
    case "$(uname -m)" in \
      x86_64)  ABBENAY_ARCH="x64"  ;; \
      aarch64) ABBENAY_ARCH="arm64" ;; \
      *) echo "Unsupported arch: $(uname -m)" >&2; exit 1 ;; \
    esac; \
    wget -O /tmp/abbenay.tar.gz \
      "https://github.com/redhat-developer/abbenay/releases/download/${ABBENAY_VERSION}/abbenay-${ABBENAY_VERSION#v}-linux-${ABBENAY_ARCH}.tar.gz"; \
    echo "${ABBENAY_SHA256}  /tmp/abbenay.tar.gz" | sha256sum -c -; \
    tar xzf /tmp/abbenay.tar.gz -C /opt/abbenay; \
    rm /tmp/abbenay.tar.gz; \
    chmod +x "/opt/abbenay/abbenay-daemon-linux-${ABBENAY_ARCH}"; \
    ln -s "/opt/abbenay/abbenay-daemon-linux-${ABBENAY_ARCH}" /usr/local/bin/abbenay

COPY containers/abbenay/config.yaml /root/.config/abbenay/config.yaml

EXPOSE 50057

CMD ["abbenay", "daemon", "--grpc-host", "0.0.0.0", "--grpc-port", "50057"]
