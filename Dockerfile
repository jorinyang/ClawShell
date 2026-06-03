# ── ClawShell Edge Docker Image ──
# Build:  docker build -t clawshell-edge .
# Run:    docker run -d --name clawshell-edge \
#           -v ~/.clawshell/data:/root/.clawshell/data \
#           -v ~/.clawshell/.env:/root/.clawshell/.env \
#           --network host \
#           clawshell-edge

FROM python:3.11-slim

LABEL org.clawshell.version="2.2.0"
LABEL org.clawshell.component="edge-brain"

# ── System deps ──
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ── ClawShell ──
WORKDIR /root/.clawshell

# Clone and install
ARG CLAWSHELL_REPO=https://github.com/jorinyang/ClawShell.git
RUN git clone --depth 1 ${CLAWSHELL_REPO} . && \
    pip install --no-cache-dir pyyaml requests aiohttp websockets

# ── Optional: MemPalace (memory plugin) ──
RUN git clone --depth 1 https://github.com/mempalace/mempalace.git /root/.mempalace 2>/dev/null || true
RUN cd /root/.mempalace && pip install --no-cache-dir -e . 2>/dev/null || true

# ── Optional: MemOS Cloud Plugin ──
RUN pip install --no-cache-dir memos-local-plugin 2>/dev/null || true

# ── Runtime dirs ──
RUN mkdir -p /root/.clawshell/data /root/.hermes /root/.openclaw

# ── Health check ──
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python3 -c "from edge.mcp.edge_server import main; print('OK')" || exit 1

# ── Entrypoint ──
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["daemon"]
