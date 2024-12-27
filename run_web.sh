#!/bin/bash

sudo killall gunicorn
source venv/bin/activate
source .env

pushd ~/riddler/web/web

current_date=$(date +%Y-%m-%d)
sudo ../../venv/bin/gunicorn main:app               \
    --bind 0.0.0.0:443                              \
    --certfile "$SSL_CERT"                          \
    --keyfile "$SSL_KEY"                            \
    --workers 4                                     \
    --worker-class uvicorn.workers.UvicornWorker    \
    --access-logfile "-"                            \
    | tee -a "$HOME/logs/web-$current_date.log"

popd
