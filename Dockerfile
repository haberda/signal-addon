FROM bbernhard/signal-cli-rest-api:0.38

LABEL io.hass.version="0.38" io.hass.type="addon" io.hass.arch="armhf|aarch64|amd64"

COPY options.sh /options.sh

RUN ["chmod", "+x", "/options.sh"]

RUN apt-get clean \

        && apt-get update \

        && apt-get install -y --no-install-recommends jq

WORKDIR /data/data/

ENTRYPOINT ["/options.sh"]

VOLUME ["/data"]
