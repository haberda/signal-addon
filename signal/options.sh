#!/usr/bin/env bash
set -euo pipefail

CONFIG_PATH=/data/options.json

# The upstream image runs as signal-api (UID/GID 1000). Supervisor mounts the
# add-on config directory with host ownership, so make the persisted Signal
# state writable before the rootless services start. Only touch entries that
# need it so large attachment stores do not slow every boot.
mkdir -p /config
find /config \( ! -uid 1000 -o ! -gid 1000 \) -exec chown -h 1000:1000 {} +

ENV_DIR=/run/signal-addon
mkdir -p "$ENV_DIR"
ENV_FILE=$(mktemp "$ENV_DIR/options.env.XXXXXX")
trap 'rm -f "$ENV_FILE"' EXIT

write_env() {
	local key=$1 value=$2 escaped
	escaped=${value//\\/\\\\}
	escaped=${escaped//\'/\'\\\'\'}
	printf "export %s='%s'\n" "$key" "$escaped" >> "$ENV_FILE"
}

# Read a string option, falling back to a default when it is absent or empty.
option() {
	jq --raw-output --arg key "$1" --arg default "$2" \
		'if (.[$key] // "") == "" then $default else .[$key] | tostring end' "$CONFIG_PATH"
}

# Read a boolean option. Do not use jq's // here: it treats false as absent.
bool_option() {
	jq --raw-output --arg key "$1" --argjson default "$2" \
		'if .[$key] == null then $default else .[$key] end' "$CONFIG_PATH"
}

MODE=$(option mode normal)
write_env MODE "$MODE"

WEBUI_ENABLED=$(bool_option WEBUI_ENABLED true)
write_env WEBUI_ENABLED "$WEBUI_ENABLED"

write_env DEFAULT_SIGNAL_TEXT_MODE "$(option DEFAULT_SIGNAL_TEXT_MODE normal)"

LOG_LEVEL=$(option LOG_LEVEL info)
write_env LOG_LEVEL "$LOG_LEVEL"
write_env SIGNAL_CLI_CONFIG_DIR "${SIGNAL_CLI_CONFIG_DIR:-/config}"

if [ "$MODE" = "json-rpc" ] || [ "$MODE" = "json-rpc-native" ]; then
	write_env JSON_RPC_TRUST_NEW_IDENTITIES "$(option JSON_RPC_TRUST_NEW_IDENTITIES on-first-use)"
	for media in ATTACHMENTS STORIES AVATARS STICKERS; do
		write_env "JSON_RPC_IGNORE_$media" "$(bool_option "JSON_RPC_IGNORE_$media" false)"
	done

	RECEIVE_WEBHOOK_URL=$(option RECEIVE_WEBHOOK_URL "")
	if [ -n "$RECEIVE_WEBHOOK_URL" ]; then
		write_env RECEIVE_WEBHOOK_URL "$RECEIVE_WEBHOOK_URL"
	fi
else
	if [ "$(bool_option AUTO_RECEIVE false)" = "true" ]; then
		write_env AUTO_RECEIVE_SCHEDULE "$(option AUTO_RECEIVE_SCHEDULE '0 22 * * *')"
	fi

	SIGNAL_CLI_CMD_TIMEOUT=$(option SIGNAL_CLI_CMD_TIMEOUT "")
	if [ -n "$SIGNAL_CLI_CMD_TIMEOUT" ] && [ "$SIGNAL_CLI_CMD_TIMEOUT" -gt 0 ]; then
		write_env SIGNAL_CLI_CMD_TIMEOUT "$SIGNAL_CLI_CMD_TIMEOUT"
	fi
fi

chmod 0644 "$ENV_FILE"
mv "$ENV_FILE" "$ENV_DIR/options.env"

# Do not print the webhook URL; it may contain a Home Assistant webhook secret.
if [ "$LOG_LEVEL" = "debug" ]; then
	echo "Effective Signal add-on options:"
	sed -e 's/^/  /' -e "s/^\(  export RECEIVE_WEBHOOK_URL=\).*/\1'<redacted>'/" "$ENV_DIR/options.env"
fi
