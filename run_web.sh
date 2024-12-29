#!/bin/bash

sudo killall gunicorn
source venv/bin/activate
source .env

pushd ~/riddler/web/web

current_date=$(date +%Y-%m-%d)
log_file="$HOME/logs/web-$current_date.log"
nohup sudo ../../venv/bin/gunicorn main:app         \
    --bind 0.0.0.0:443                              \
    --certfile "$SSL_CERT"                          \
    --keyfile "$SSL_KEY"                            \
    --workers 4                                     \
    --worker-class uvicorn.workers.UvicornWorker    \
    --access-logfile "-"                            \
    &>> $log_file &
sleep .5
tail -f $log_file

popd
