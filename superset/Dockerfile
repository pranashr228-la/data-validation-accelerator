FROM apache/superset:4.1.2

USER root

# Trust corporate/system CA bundle (same pattern as the main DVA Dockerfile).
COPY certs/system-ca-bundle.pem /usr/local/share/ca-certificates/system-ca-bundle.crt
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
    PIP_CERT=/etc/ssl/certs/ca-certificates.crt

# Install at build time (not runtime) so corporate TLS proxies do not break startup.
RUN pip install --no-cache-dir psycopg2-binary

COPY superset/bootstrap/entrypoint.sh /app/bootstrap/entrypoint.sh
RUN chmod +x /app/bootstrap/entrypoint.sh

USER superset

CMD ["/app/bootstrap/entrypoint.sh"]
