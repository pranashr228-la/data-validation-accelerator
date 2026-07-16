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

`dva` auto-loads this bundle for Snowflake/HTTPS clients when the file exists
(see `src/dva/config/certs.py`). If Snowflake fails with `certificate verify failed`
behind Zscaler, regenerate this file and retry.
