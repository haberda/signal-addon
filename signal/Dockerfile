ARG BUILD_FROM=bbernhard/signal-cli-rest-api:0.60
# hadolint ignore=DL3006
FROM ${BUILD_FROM}

COPY options.sh /options.sh

RUN ["chmod", "+x", "/options.sh"]

RUN apt-get clean \

        && apt-get update \

        && apt-get install -y --no-install-recommends jq

WORKDIR /data/data/

ENTRYPOINT ["/options.sh"]

VOLUME ["/data"]

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
    org.label-schema.name="Nextcloud" \
    org.label-schema.schema-version="${BUILD_VERSION}" \
    org.label-schema.url="https://github.com/haberda/signal-addon" \
    org.label-schema.usage="https://github.com/haberda/signal-addon" \
    org.label-schema.vcs-ref="${BUILD_REF}" \
    org.label-schema.vcs-url="https://github.com/haberda/" \
    org.label-schema.vendor="No Vendor"
