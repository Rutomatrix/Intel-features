#!/bin/bash

# Folder where logs will be stored
LOGDIR="/home/rpi/serial_logs"

# Create the folder if it doesnâ€™t exist
mkdir -p "$LOGDIR"

# Create filename with date & time
LOGFILE="$LOGDIR/BIOS_LOG_$(date +%d-%m-%y-%H-%M).txt"

echo "---------------------------------------------------"
echo "Serial logging started..."
echo "Port    : /dev/ttyUSB0"
echo "Baud    : 115200"
echo "Log file: $LOGFILE"
echo "---------------------------------------------------"

# Run picocom and log output
#picocom -b 115200 /dev/ttyUSB0 | tee "$LOGFILE"

picocom -b 115200 --nolock /dev/ttyUSB0 | tee "$LOGFILE"
