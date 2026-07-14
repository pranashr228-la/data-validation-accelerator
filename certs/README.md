# certs/

`system-ca-bundle.pem` is exported from the local macOS System/System Roots
keychains so `pip`/`uv` inside the Docker build can reach PyPI through a
TLS-inspecting corporate proxy (the same reason `uv --system-certs` is used
on the host). Regenerate it if the build starts failing with SSL errors:

```bash
security find-certificate -a -p /Library/Keychains/System.keychain > certs/system-ca-bundle.pem
security find-certificate -a -p /System/Library/Keychains/SystemRootCertificates.keychain >> certs/system-ca-bundle.pem
```

These are root CA certificates (public keys), not secrets.
