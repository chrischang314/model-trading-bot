ARG KDB_BASE_IMAGE=kdb-insights-core:latest
FROM ${KDB_BASE_IMAGE}

WORKDIR /opt/kx

ENV KDB_DATA_DIR=/data/kdb \
    KDB_PORT=5000

COPY q /opt/kx/q

VOLUME ["/data/kdb"]
EXPOSE 5000

ENTRYPOINT ["/bin/sh", "-c", "set -eu; if command -v q >/dev/null 2>&1; then exec q /opt/kx/q/init.q -p ${KDB_PORT}; elif [ -x /opt/kx/kdb/l64/q ]; then exec /opt/kx/kdb/l64/q /opt/kx/q/init.q -p ${KDB_PORT}; else echo 'q binary not found in KDB base image' >&2; exit 1; fi"]

