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

export MODE=$(jq --raw-output '.mode // empty' $CONFIG_PATH)
#echo "export MODE=$(jq --raw-output '.mode // empty' $CONFIG_PATH)" >> /etc/bash.bashrc

if [ "${MODE_tmp}" != "json-rpc" ]; then

	if [ $AUTO_RECEIVE_SCHEDULE_bool ]
	then
	  export AUTO_RECEIVE_SCHEDULE='0 22 * * *'
	  #echo "export AUTO_RECEIVE_SCHEDULE='0 22 * * *'" >> /etc/bash.bashrc
	fi

	if [ $SIGNAL_CLI_CMD_TIMEOUT_tmp -ne 0 ]
	then
	  export SIGNAL_CLI_CMD_TIMEOUT=$(jq --raw-output '.SIGNAL_CLI_CMD_TIMEOUT // empty' $CONFIG_PATH)
	  #echo "export SIGNAL_CLI_CMD_TIMEOUT=$(jq --raw-output '.SIGNAL_CLI_CMD_TIMEOUT // empty' $CONFIG_PATH)" >> /etc/bash.bashrc
	fi

fi


#source /etc/bash.bashrc

sh /entrypoint.sh
