ARG BUILD_FROM
# hadolint ignore=DL3006
FROM ${BUILD_FROM}

COPY options.sh /options.sh

# Keep jq aligned with security updates in the upstream Ubuntu base image.
# hadolint ignore=DL3008
RUN chmod +x /options.sh \
        && apt-get clean \
        && apt-get update \
        && apt-get install -y --no-install-recommends jq \
        && rm -rf /var/lib/apt/lists/*

ENTRYPOINT ["/options.sh"]

VOLUME ["/config"]

# Build arugments
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
    org.label-schema.vcs-url="https://github.com/haberda/" \
    org.label-schema.vendor="No Vendor"
