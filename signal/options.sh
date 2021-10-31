#!/usr/bin/env bash
set -e

CONFIG_PATH=/data/options.json

#export USE_NATIVE=$(jq --raw-output '.native_mode // empty' $CONFIG_PATH)

export MODE=$(jq --raw-output '.mode // empty' $CONFIG_PATH)

export AUTO_RECEIVE_SCHEDULE_bool=$(jq --raw-output '.AUTO_RECEIVE // empty' $CONFIG_PATH)

export SIGNAL_CLI_CMD_TIMEOUT=$(jq --raw-output '.SIGNAL_CLI_CMD_TIMEOUT // empty' $CONFIG_PATH)

if [ $AUTO_RECEIVE_SCHEDULE_bool == '1' ]
then
  export AUTO_RECEIVE_SCHEDULE="0 22 * * *"
fi

echo "Native mode:"
echo "${USE_NATIVE}"
echo "Mode:"
echo "${MODE}"
echo "AUTO RECEIVE SCHEDULE:"
echo "${AUTO_RECEIVE_SCHEDULE}"
echo "Signal-cli command timeout:"
echo $SIGNAL_CLI_CMD_TIMEOUT

sh /entrypoint.sh
