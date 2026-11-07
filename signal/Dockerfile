ARG BUILD_FROM
# hadolint ignore=DL3006
FROM ${BUILD_FROM}

COPY options.sh /etc/cont-init.d/00-signal-options
COPY webui /opt/signal-webui
COPY webui-service /etc/s6-overlay/s6-rc.d/signal-webui
COPY s6-services /etc/s6-overlay/s6-rc.d

# The upstream 0.101 image is rootless and sets USER signal-api in its final
# stage. Package installation still needs root; runtime services stay unprivileged.
# s6-overlay must be PID 1. The cont-init script reads Supervisor's protected
# options file as root, while each service drops to the rootless signal-api user.
# hadolint ignore=DL3002
USER root
# hadolint ignore=DL3008
RUN chmod 755 /etc/cont-init.d/00-signal-options \
        /etc/s6-overlay/s6-rc.d/signal-webui/run \
        /etc/s6-overlay/s6-rc.d/signal-api/run \
        /etc/s6-overlay/s6-rc.d/signal-json-rpc/run \
        && apt-get update \
        && apt-get install -y --no-install-recommends jq python3 python3-pil python3-qrcode \
        && apt-get clean \
        && rm -rf /var/lib/apt/lists/*

ENTRYPOINT ["/init"]

# Supervisor restarts an unhealthy add-on when its Watchdog switch is on.
# JSON-RPC modes start slowly, so allow a generous start period.
HEALTHCHECK --interval=60s --timeout=10s --start-period=180s --retries=3 \
    CMD ["curl", "--fail", "--silent", "--max-time", "8", "http://127.0.0.1:8080/v1/health"]

VOLUME ["/config"]

# Build arguments
ARG BUILD_ARCH
ARG BUILD_DATE
ARG BUILD_REF
ARG BUILD_VERSION

# Labels
LABEL \
    io.hass.name="Signal Messenger" \
    io.hass.description="Signal Messenger" \
    io.hass.arch="${BUILD_ARCH}" \
    io.hass.version="${BUILD_VERSION}" \
    io.hass.type="addon" \
    maintainer="haberda" \
    org.label-schema.description="Signal Messenger" \
    org.label-schema.build-date="${BUILD_DATE}" \
    org.label-schema.name="Signal Messenger" \
    org.label-schema.schema-version="${BUILD_VERSION}" \
    org.label-schema.url="https://github.com/haberda/signal-addon" \
    org.label-schema.usage="https://github.com/haberda/signal-addon" \
    org.label-schema.vcs-ref="${BUILD_REF}" \
    org.label-schema.vcs-url="https://github.com/haberda/signal-addon" \
    org.label-schema.vendor="No Vendor"
