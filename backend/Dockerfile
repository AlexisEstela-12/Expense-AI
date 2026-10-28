# Context: backend/. Target: Linux x86_64 / CPython 3.13 / Debian Bookworm.
# Official Docker Hub linux/amd64 manifest, verified on 2026-10-27.
FROM python:3.13.18-slim-bookworm@sha256:89c04d97d1f3f0a04ea357a27d000ba4efb18536d2d68a54611f76d5c1b5fe99 AS runtime-base

# Freeze Debian indexes while retaining archive signature verification.
# Expiry checks are disabled only for historical snapshots, not signatures.
RUN set -eu; \
    test "$(dpkg --print-architecture)" = amd64; \
    rm -f /etc/apt/sources.list /etc/apt/sources.list.d/debian.sources; \
    printf '%s\n' \
      'deb [check-valid-until=no signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] https://snapshot.debian.org/archive/debian/20261027T000000Z bookworm main' \
      'deb [check-valid-until=no signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] https://snapshot.debian.org/archive/debian-security/20261027T000000Z bookworm-security main' \
      > /etc/apt/sources.list.d/debian-snapshot.list; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates curl libgssapi-krb5-2 unixodbc odbcinst; \
    curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 \
      https://packages.microsoft.com/config/debian/12/packages-microsoft-prod.deb \
      --output /tmp/packages-microsoft-prod.deb; \
    echo '8434dcb8c346dc95fbd63dbece056c343704590b58b6a5c323d39acf52bf0b48  /tmp/packages-microsoft-prod.deb' | sha256sum --check -; \
    dpkg -i /tmp/packages-microsoft-prod.deb; \
    printf '%s\n' \
      'Package: msodbcsql18' 'Pin: origin packages.microsoft.com' 'Pin-Priority: 500' '' \
      'Package: *' 'Pin: origin packages.microsoft.com' 'Pin-Priority: -1' \
      > /etc/apt/preferences.d/microsoft-odbc-only; \
    apt-get update; \
    cd /tmp; \
    apt-get download msodbcsql18=18.7.1.1-1; \
    echo 'f506cb3de8b34cd94e9014d247b39e9dfd7effad79edad3ab67096dc3c1b6b0e  msodbcsql18_18.7.1.1-1_amd64.deb' | sha256sum --check -; \
    ACCEPT_EULA=Y apt-get install -y --no-install-recommends ./msodbcsql18_18.7.1.1-1_amd64.deb; \
    test "$(dpkg-query -W -f='${Version}' msodbcsql18)" = 18.7.1.1-1; \
    dpkg --verify msodbcsql18; \
    odbcinst -q -d -n 'ODBC Driver 18 for SQL Server'; \
    apt-get purge -y --auto-remove curl; \
    rm -f /tmp/packages-microsoft-prod.deb /tmp/msodbcsql18_18.7.1.1-1_amd64.deb; \
    rm -rf /var/lib/apt/lists/*

FROM runtime-base AS dependencies
COPY requirements.lock /tmp/requirements.lock
RUN python -m venv /opt/venv \
    && /opt/venv/bin/python -m pip install --no-cache-dir --only-binary=:all: \
         --require-hashes -r /tmp/requirements.lock \
    && /opt/venv/bin/python -m pip check

FROM runtime-base AS runtime
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
RUN groupadd --gid 10001 expense \
    && useradd --uid 10001 --gid 10001 --no-create-home \
         --home-dir /nonexistent --shell /usr/sbin/nologin expense

COPY --from=dependencies /opt/venv /opt/venv
COPY main.py ./main.py
COPY api/ ./api/
COPY chat/ ./chat/
COPY core/ ./core/
COPY db/ ./db/
COPY llm/ ./llm/
COPY schemas/ ./schemas/
COPY services/ ./services/

USER 10001:10001
EXPOSE 8000
# Process health only: no database or provider calls.
HEALTHCHECK --interval=30s --timeout=3s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).close()"]
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
