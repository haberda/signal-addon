#!/usr/bin/env bash
set -e

CONFIG_PATH=/data/options.json

export MODE_tmp=$(jq --raw-output '.mode // empty' "$CONFIG_PATH")

export AUTO_RECEIVE_SCHEDULE_bool=$(jq --raw-output '.AUTO_RECEIVE // empty' "$CONFIG_PATH")

export SIGNAL_CLI_CMD_TIMEOUT_tmp=$(jq --raw-output '.SIGNAL_CLI_CMD_TIMEOUT // empty' "$CONFIG_PATH")

export reset_data=$(jq --raw-output '.reset_data // empty' "$CONFIG_PATH")

export MODE=$(jq --raw-output '.mode // empty' "$CONFIG_PATH")

export DEFAULT_SIGNAL_TEXT_MODE=$(jq --raw-output '.DEFAULT_SIGNAL_TEXT_MODE // "normal"' $CONFIG_PATH)

if [ "${MODE_tmp}" != "json-rpc" ] && [ "${MODE_tmp}" != "json-rpc-native" ]; then

	if [ "${AUTO_RECEIVE_SCHEDULE_bool}" = "true" ]
	then
	  export AUTO_RECEIVE_SCHEDULE='0 22 * * *'
	fi

	if [ -n "${SIGNAL_CLI_CMD_TIMEOUT_tmp}" ] && [ "${SIGNAL_CLI_CMD_TIMEOUT_tmp}" -ne 0 ]
	then
	  export SIGNAL_CLI_CMD_TIMEOUT="${SIGNAL_CLI_CMD_TIMEOUT_tmp}"
	fi

fi

sh /entrypoint.sh
