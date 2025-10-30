#!/bin/bash
# -------------------------------
# Script to set global IP in /etc/environment
# -------------------------------

IP_VALUE="0.0.0.0"   # <-- You can change this to your IP value

# Check if IP already exists in /etc/environment
if grep -q '^IP=' /etc/environment; then
  sudo sed -i "s|^IP=.*|IP=\"$IP_VALUE\"|" /etc/environment
else
  echo "IP=\"$IP_VALUE\"" | sudo tee -a /etc/environment > /dev/null
fi

# Reload environment
source /etc/environment

echo "✅ Global IP set to: $IP"