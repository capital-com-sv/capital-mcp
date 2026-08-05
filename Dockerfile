FROM python:3.10-alpine AS builder

WORKDIR /app

COPY pyproject.toml ./
COPY capital_mcp/ capital_mcp/

RUN pip install --no-cache-dir \
    --trusted-host pypi.org \
    --trusted-host pypi.python.org \
    --trusted-host files.pythonhosted.org \
    .


FROM python:3.10-alpine

ARG VERSION=0.1.0
ARG SOURCE_URL=https://github.com/capital-com-sv/capital-mcp

LABEL org.opencontainers.image.title="Capital.com MCP Server" \
      org.opencontainers.image.description="MCP server for Capital.com Open API — LLM-driven trading via Model Context Protocol" \
      org.opencontainers.image.source="${SOURCE_URL}" \
      org.opencontainers.image.url="${SOURCE_URL}" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.vendor="Capital.com"

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /app/capital_mcp /app/capital_mcp

RUN adduser -D -s /bin/sh mcp
USER mcp

ENTRYPOINT ["python", "-m", "capital_mcp.server"]