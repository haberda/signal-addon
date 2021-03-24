#!/usr/bin/env bash
set -e

CONFIG_PATH=/data/options.json

export USE_NATIVE=$(jq --raw-output '.native_mode // empty' $CONFIG_PATH)

echo "${USE_NATIVE}"

sh /entrypoint.sh
