#!/bin/bash

source venv/bin/activate
source .env
pushd ~/riddler/web/web
sudo ../../venv/bin/uvicorn main:app    \
    --host 0.0.0.0                      \
    --port 443                          \
    --ssl-certfile "$SSL_CERT"          \
    --ssl-keyfile "$SSL_KEY"            \
    --use-colors                        \
    --workers 4
popd
