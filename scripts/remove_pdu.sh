#!/usr/bin/env bash
# ---------------------------------------------------------
# remove_pdu.sh
# Stops/removes PDU service and files from the Pi.
# ---------------------------------------------------------
set -euo pipefail

SERVICE_NAME="pdu.service"
SYSTEMD_PATH="/etc/systemd/system/${SERVICE_NAME}"

TARGET_USER="${SUDO_USER:-rpi}"
TARGET_HOME="/home/${TARGET_USER}"
APP_DIR="${TARGET_HOME}/PDU"
TMP_CLONE="/tmp/pdu_repo"

echo "=== Removing PDU setup ==="

# 1) Stop & disable systemd service, remove unit file
if systemctl list-unit-files | grep -q "^${SERVICE_NAME}"; then
  echo "--- Stopping and disabling ${SERVICE_NAME} ---"
  systemctl stop "${SERVICE_NAME}" || true
  systemctl disable "${SERVICE_NAME}" || true
  rm -f "${SYSTEMD_PATH}" || true
  systemctl daemon-reload
else
  echo "No systemd unit named ${SERVICE_NAME} found (skipping)."
fi

# 2) Remove application directory
if [[ -d "${APP_DIR}" ]]; then
  echo "--- Removing ${APP_DIR} ---"
  rm -rf "${APP_DIR}"
else
  echo "${APP_DIR} not found (skipping)."
fi

# 3) Remove temp clone dir (if any)
if [[ -d "${TMP_CLONE}" ]]; then
  echo "--- Cleaning temp clone ${TMP_CLONE} ---"
  rm -rf "${TMP_CLONE}"
fi

# 4) (Optional) Clean pip cache for the app user
echo "--- (Optional) Cleaning pip cache ---"
sudo -u "${TARGET_USER}" bash -lc "pip cache purge" || true

echo
echo "✅ PDU removed."
echo "Verify:"
echo "  systemctl status ${SERVICE_NAME} || true"
echo "  ls -la ${TARGET_HOME}"
