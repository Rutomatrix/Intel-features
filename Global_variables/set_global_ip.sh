#!/bin/bash
# -------------------------------
# Script to set global IP and RPI_NAME in /etc/environment
# -------------------------------

IP_VALUE="100.109.50.57"        # <-- You can change this to your IP value
RPI_NAME_VALUE="Intel-RPI-01"   # <-- You can change this to your RPI name

# -------------------------------
# Function to update or add a variable
# -------------------------------
update_env_var() {
  local var_name=$1
  local var_value=$2

  if grep -q "^${var_name}=" /etc/environment; then
    sudo sed -i "s|^${var_name}=.*|${var_name}=\"${var_value}\"|" /etc/environment
  else
    echo "${var_name}=\"${var_value}\"" | sudo tee -a /etc/environment > /dev/null
  fi
}

# -------------------------------
# Update IP and RPI_NAME
# -------------------------------
update_env_var "IP" "$IP_VALUE"
update_env_var "RPI_NAME" "$RPI_NAME_VALUE"

# Reload environment variables
source /etc/environment

echo "✅ Global variables updated successfully!"
echo "🌐 IP: $IP"
echo "💻 RPI_NAME: $RPI_NAME"
