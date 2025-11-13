#!/bin/bash
set -e

echo "Running first command..."
sudo raspi-gpio set 20 op dh

echo "Running second command..."
sudo i2cset -y 1 0x72 2

echo "All commands executed successfully!"
