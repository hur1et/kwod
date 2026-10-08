FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends chromium nodejs npm git curl ca-certificates build-essential pkg-config \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir playwright==1.63.0 requests==2.34.2
COPY browser_session.py /opt/kwod/browser_session.py
WORKDIR /workspace
USER 65532:65532
ENTRYPOINT ["/bin/sh"]
