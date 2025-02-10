#!/bin/bash

killall python3
source ~/riddler/venv/bin/activate

pushd ~/riddler/bot

current_date=$(date +%Y-%m-%d)
log_file="$HOME/logs/bot-$current_date.log"
nohup python3 . &>> "$log_file" &
sleep .5
tail -f $log_file

popd
