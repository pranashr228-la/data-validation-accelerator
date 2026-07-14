FROM python:3.14-slim

WORKDIR /app

# Trust the host's corporate/system CA bundle (if provided) so pip/uv can
# reach PyPI through a TLS-inspecting proxy. See certs/README.md.
COPY certs/system-ca-bundle.pem /usr/local/share/ca-certificates/system-ca-bundle.crt
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
    PIP_CERT=/etc/ssl/certs/ca-certificates.crt \
    UV_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock* ./
COPY src ./src
COPY configs ./configs
COPY sql ./sql
COPY sample_data ./sample_data

RUN uv sync --no-dev --system-certs || uv sync --system-certs

ENTRYPOINT ["uv", "run", "--no-sync", "dva"]
