#!/bin/bash

sudo killall hypercorn
source venv/bin/activate
source .env

pushd ~/riddler/web/web

current_date=$(date +%Y-%m-%d)
log_file="$HOME/logs/web-$current_date.log"
nohup sudo ../../venv/bin/hypercorn     \
    main:app                            \
    --bind 0.0.0.0:443                  \
    --certfile "$SSL_CERT"              \
    --keyfile "$SSL_KEY"                \
    --workers 4                         \
    --access-logfile "-"                \
    &>> $log_file &
sleep .5
tail -f $log_file

popd
