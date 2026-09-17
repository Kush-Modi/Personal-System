#!/data/data/com.termux/files/usr/bin/bash

cd ~/personal-server || exit 1

while true; do
    ./update-server.sh
    sleep 300
done

