#!/usr/bin/env bash
set -e

CONFIG_PATH=/data/options.json

export MODE_tmp=$(jq --raw-output '.mode // empty' $CONFIG_PATH)

export AUTO_RECEIVE_SCHEDULE_bool=$(jq --raw-output '.AUTO_RECEIVE // empty' $CONFIG_PATH)

export SIGNAL_CLI_CMD_TIMEOUT_tmp=$(jq --raw-output '.SIGNAL_CLI_CMD_TIMEOUT // empty' $CONFIG_PATH)

export reset_data=$(jq --raw-output '.reset_data // empty' $CONFIG_PATH)

if [ $reset_data ]
then
	rm -r /data/*
	echo "Data deleted. Please set reset_data to off and restart the addon."
	exit
fi

echo "Mode:"
echo "${MODE_tmp}"
export MODE="${MODE_tmp}"

if [ "${MODE}" != "json-rpc" ]
then
	if [ $AUTO_RECEIVE_SCHEDULE_bool ]
	then
	  export AUTO_RECEIVE_SCHEDULE="0 22 * * *"
      echo "AUTO RECEIVE SCHEDULE:"
      echo "${AUTO_RECEIVE_SCHEDULE}"
	fi

	if [ $SIGNAL_CLI_CMD_TIMEOUT_tmp -ne 0 ]
	then
	  export SIGNAL_CLI_CMD_TIMEOUT=$SIGNAL_CLI_CMD_TIMEOUT_tmp
	  echo "Signal-cli command timeout:"
      echo "$SIGNAL_CLI_CMD_TIMEOUT"
	fi
	echo "test json"
fi

sh /entrypoint.sh
