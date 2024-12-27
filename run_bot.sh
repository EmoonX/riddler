#!/bin/bash

killall python3.12
source venv/bin/activate

pushd ~/riddler/bot

current_date=$(date +%Y-%m-%d)
nohup python3.12 . | tee -a "$HOME/logs/bot-$current_date.log"

popd
