#!/usr/bin/env bash
set -euo pipefail

CONFIG_PATH=/data/options.json

ENV_DIR=/run/signal-addon
mkdir -p "$ENV_DIR"
ENV_FILE=$(mktemp "$ENV_DIR/options.env.XXXXXX")
trap 'rm -f "$ENV_FILE"' EXIT

write_env() {
	local key=$1 value=$2 escaped
	escaped=${value//\\/\\\\}
	escaped=${escaped//\'/\'\\\'\'}
	printf "%s='%s'\n" "$key" "$escaped" >> "$ENV_FILE"
}

MODE_tmp=$(jq --raw-output '.mode // empty' "$CONFIG_PATH")

AUTO_RECEIVE_SCHEDULE_bool=$(jq --raw-output '.AUTO_RECEIVE // empty' "$CONFIG_PATH")

SIGNAL_CLI_CMD_TIMEOUT_tmp=$(jq --raw-output '.SIGNAL_CLI_CMD_TIMEOUT // empty' "$CONFIG_PATH")

MODE=$(jq --raw-output '.mode // empty' "$CONFIG_PATH")
write_env MODE "$MODE"

WEBUI_ENABLED=$(jq --raw-output '.WEBUI_ENABLED // true' "$CONFIG_PATH")
write_env WEBUI_ENABLED "$WEBUI_ENABLED"

DEFAULT_SIGNAL_TEXT_MODE=$(jq --raw-output '.DEFAULT_SIGNAL_TEXT_MODE // "normal"' "$CONFIG_PATH")
write_env DEFAULT_SIGNAL_TEXT_MODE "$DEFAULT_SIGNAL_TEXT_MODE"

LOG_LEVEL=$(jq --raw-output '.LOG_LEVEL // "info"' "$CONFIG_PATH")
write_env LOG_LEVEL "$LOG_LEVEL"
write_env SIGNAL_CLI_CONFIG_DIR "${SIGNAL_CLI_CONFIG_DIR:-/config}"

if [ "${MODE_tmp}" = "json-rpc" ] || [ "${MODE_tmp}" = "json-rpc-native" ]; then

	JSON_RPC_TRUST_NEW_IDENTITIES=$(jq --raw-output '.JSON_RPC_TRUST_NEW_IDENTITIES // "on-first-use"' "$CONFIG_PATH")
	write_env JSON_RPC_TRUST_NEW_IDENTITIES "$JSON_RPC_TRUST_NEW_IDENTITIES"

	JSON_RPC_IGNORE_ATTACHMENTS=$(jq --raw-output '.JSON_RPC_IGNORE_ATTACHMENTS // false' "$CONFIG_PATH")
	write_env JSON_RPC_IGNORE_ATTACHMENTS "$JSON_RPC_IGNORE_ATTACHMENTS"

	JSON_RPC_IGNORE_STORIES=$(jq --raw-output '.JSON_RPC_IGNORE_STORIES // false' "$CONFIG_PATH")
	write_env JSON_RPC_IGNORE_STORIES "$JSON_RPC_IGNORE_STORIES"

	JSON_RPC_IGNORE_AVATARS=$(jq --raw-output '.JSON_RPC_IGNORE_AVATARS // false' "$CONFIG_PATH")
	write_env JSON_RPC_IGNORE_AVATARS "$JSON_RPC_IGNORE_AVATARS"

	JSON_RPC_IGNORE_STICKERS=$(jq --raw-output '.JSON_RPC_IGNORE_STICKERS // false' "$CONFIG_PATH")
	write_env JSON_RPC_IGNORE_STICKERS "$JSON_RPC_IGNORE_STICKERS"

else

	if [ "${AUTO_RECEIVE_SCHEDULE_bool}" = "true" ]
	then
	  write_env AUTO_RECEIVE_SCHEDULE '0 22 * * *'
	fi

	if [ -n "${SIGNAL_CLI_CMD_TIMEOUT_tmp}" ] && [ "${SIGNAL_CLI_CMD_TIMEOUT_tmp}" -ne 0 ]
	then
	  write_env SIGNAL_CLI_CMD_TIMEOUT "${SIGNAL_CLI_CMD_TIMEOUT_tmp}"
	fi

fi

chmod 0644 "$ENV_FILE"
mv "$ENV_FILE" "$ENV_DIR/options.env"
