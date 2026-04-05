#!/bin/bash

sudo killall uvicorn
source ~/riddler/.env

pushd ~/riddler/web/web

uvicorn="../../.venv/bin/uvicorn"
params="
    --host 127.0.0.1
    --port 8000
    --workers 4
    --access-log
    --use-colors
"
current_date=$(date +%Y-%m-%d)
log_file="$HOME/logs/web-$current_date.log"

sudo nohup $uvicorn main:app $params &>> $log_file &
sleep .5
tail -f $log_file

popd
