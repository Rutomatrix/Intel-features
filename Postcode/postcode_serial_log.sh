#!/bin/bash

# Folder where postcode logs will be stored
LOGDIR="/home/rpi/postcode_logs"

# Serial configuration
PORT="/dev/ttyAMA0"
BAUDRATE="115200"

# Create the folder if it doesn't exist
mkdir -p "$LOGDIR"

# Create filename with date & time
LOGFILE="$LOGDIR/POSTCODE_LOG_$(date +%d-%m-%y-%H-%M).txt"

echo "---------------------------------------------------"
echo "Postcode serial logging started..."
echo "Port    : $PORT"
echo "Baud    : $BAUDRATE"
echo "Log file: $LOGFILE"
echo "---------------------------------------------------"

# Start minicom and capture logs
# -C : capture file
sudo minicom -b "$BAUDRATE" -o -D "$PORT" -C "$LOGFILE"