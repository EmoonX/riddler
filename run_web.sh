#!/bin/bash

sudo killall uvicorn
source ~/riddler/.env

pushd ~/riddler/web/web

current_date=$(date +%Y-%m-%d)
log_file="$HOME/logs/web-$current_date.log"
sudo nohup ../../venv/bin/uvicorn   \
    main:app                        \
    --host 0.0.0.0                  \
    --port 443                      \
    --ssl-certfile "$SSL_CERT"      \
    --ssl-keyfile "$SSL_KEY"        \
    --workers 2                     \
    --access-log                    \
    --use-colors                    \
    &>> $log_file                   \
    &
sleep .5
tail -f $log_file

popd
