#!/bin/sh
set -eu

cp /run/bike-mqtt/passwords /run/bike-mqtt/acl /run/bike-mqtt/health.password \
    /run/bike-certs/server.key /run/bike-private/
chown mosquitto:mosquitto /run/bike-private/*
chmod 600 /run/bike-private/*
exec /docker-entrypoint.sh /usr/sbin/mosquitto -c /mosquitto/config/mosquitto.conf
