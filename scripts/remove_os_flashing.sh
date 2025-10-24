#!/usr/bin/env bash
# ---------------------------------------------------------
# rpi_remove_os_flashing.sh
# Cleans up OS_Flashing setup from Raspberry Pi
# ---------------------------------------------------------
set -euo pipefail

SERVICE_NAME="usb_mass_storage.service"
TARGET_USER="${SUDO_USER:-rpi}"
TARGET_HOME="/home/${TARGET_USER}"
OS_DIR="${TARGET_HOME}/OS_Flashing"
VENV_DIR="${OS_DIR}/venv"
SYSTEMD_PATH="/etc/systemd/system/${SERVICE_NAME}"
OS_DATA_DIR="${TARGET_HOME}/os"
TMP_CLONE="/tmp/osflashing_repo"

echo "=== Removing OS_Flashing setup ==="

# --- 1) Stop and disable systemd service ---
if systemctl list-unit-files | grep -q "${SERVICE_NAME}"; then
  echo "--- Stopping and disabling ${SERVICE_NAME} ---"
  systemctl stop "${SERVICE_NAME}" || true
  systemctl disable "${SERVICE_NAME}" || true
  systemctl daemon-reload
  rm -f "${SYSTEMD_PATH}"
else
  echo "No systemd service named ${SERVICE_NAME} found."
fi

# --- 2) Remove OS_Flashing directory ---
if [[ -d "${OS_DIR}" ]]; then
  echo "--- Removing ${OS_DIR} ---"
  rm -rf "${OS_DIR}"
else
  echo "${OS_DIR} not found, skipping."
fi

# --- 3) Remove /home/rpi/os directory ---
if [[ -d "${OS_DATA_DIR}" ]]; then
  echo "--- Removing ${OS_DATA_DIR} ---"
  rm -rf "${OS_DATA_DIR}"
else
  echo "${OS_DATA_DIR} not found, skipping."
fi

# --- 4) Remove temporary clone folder ---
if [[ -d "${TMP_CLONE}" ]]; then
  echo "--- Removing temp folder ${TMP_CLONE} ---"
  rm -rf "${TMP_CLONE}"
fi

# --- 5) Clean pip cache (optional) ---
echo "--- Cleaning pip cache ---"
sudo -u "${TARGET_USER}" bash -c "pip cache purge" || true

echo
echo "✅ OS_Flashing and related files removed successfully!"
echo "You can verify by running:"
echo "  ls /home/${TARGET_USER}/"
echo "  systemctl list-unit-files | grep ${SERVICE_NAME}"