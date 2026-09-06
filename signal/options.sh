#!/usr/bin/env bash
set -e

CONFIG_PATH=/data/options.json

MODE_tmp=$(jq --raw-output '.mode // empty' "$CONFIG_PATH")

AUTO_RECEIVE_SCHEDULE_bool=$(jq --raw-output '.AUTO_RECEIVE // empty' "$CONFIG_PATH")

SIGNAL_CLI_CMD_TIMEOUT_tmp=$(jq --raw-output '.SIGNAL_CLI_CMD_TIMEOUT // empty' "$CONFIG_PATH")

MODE=$(jq --raw-output '.mode // empty' "$CONFIG_PATH")
export MODE

DEFAULT_SIGNAL_TEXT_MODE=$(jq --raw-output '.DEFAULT_SIGNAL_TEXT_MODE // "normal"' "$CONFIG_PATH")
export DEFAULT_SIGNAL_TEXT_MODE

LOG_LEVEL=$(jq --raw-output '.LOG_LEVEL // "info"' "$CONFIG_PATH")
export LOG_LEVEL

if [ "${MODE_tmp}" = "json-rpc" ] || [ "${MODE_tmp}" = "json-rpc-native" ]; then

	JSON_RPC_TRUST_NEW_IDENTITIES=$(jq --raw-output '.JSON_RPC_TRUST_NEW_IDENTITIES // "on-first-use"' "$CONFIG_PATH")
	export JSON_RPC_TRUST_NEW_IDENTITIES

	JSON_RPC_IGNORE_ATTACHMENTS=$(jq --raw-output '.JSON_RPC_IGNORE_ATTACHMENTS // false' "$CONFIG_PATH")
	export JSON_RPC_IGNORE_ATTACHMENTS

	JSON_RPC_IGNORE_STORIES=$(jq --raw-output '.JSON_RPC_IGNORE_STORIES // false' "$CONFIG_PATH")
	export JSON_RPC_IGNORE_STORIES

	JSON_RPC_IGNORE_AVATARS=$(jq --raw-output '.JSON_RPC_IGNORE_AVATARS // false' "$CONFIG_PATH")
	export JSON_RPC_IGNORE_AVATARS

	JSON_RPC_IGNORE_STICKERS=$(jq --raw-output '.JSON_RPC_IGNORE_STICKERS // false' "$CONFIG_PATH")
	export JSON_RPC_IGNORE_STICKERS

else

	if [ "${AUTO_RECEIVE_SCHEDULE_bool}" = "true" ]
	then
	  export AUTO_RECEIVE_SCHEDULE='0 22 * * *'
	fi

	if [ -n "${SIGNAL_CLI_CMD_TIMEOUT_tmp}" ] && [ "${SIGNAL_CLI_CMD_TIMEOUT_tmp}" -ne 0 ]
	then
	  export SIGNAL_CLI_CMD_TIMEOUT="${SIGNAL_CLI_CMD_TIMEOUT_tmp}"
	fi

fi

exec /entrypoint.sh
