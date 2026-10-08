FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends chromium nodejs npm git curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir playwright requests
WORKDIR /workspace
USER 65532:65532
ENTRYPOINT ["/bin/sh"]
