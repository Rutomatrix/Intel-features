#!/usr/bin/env bash
# ---------------------------------------------------------
# rpi_remove_streaming_hid.sh
# Stops, disables, and removes the Streaming_HID stack:
#   - composite-gadget.service
#   - start_streaming.service
#   - streaming_hid.service
# Also removes /home/<user>/Streaming_HID
# ---------------------------------------------------------
set -euo pipefail

TARGET_USER="${SUDO_USER:-rpi}"
TARGET_HOME="/home/${TARGET_USER}"
STREAM_DIR="${TARGET_HOME}/Streaming_HID"
SYSTEMD_DIR="/etc/systemd/system"

SERVICES=(
  "streaming_hid.service"
  "start_streaming.service"
  "composite-gadget.service"
)

echo "=== Removing Streaming_HID stack ==="
echo "User:        ${TARGET_USER}"
echo "Stream dir:  ${STREAM_DIR}"
echo

# --- 0) (Optional) Unbind USB gadget to avoid "device busy" ---
UDC_FILE="/sys/kernel/config/usb_gadget/composite_gadget/UDC"
if [[ -e "${UDC_FILE}" ]]; then
  echo "--- Unbinding USB gadget (UDC) ---"
  # Read current UDC (if any) then unbind by writing empty string
  CURRENT_UDC="$(tr -d '\0' < "${UDC_FILE}" || true)"
  echo "" > "${UDC_FILE}" || true
  echo "Unbound from: ${CURRENT_UDC:-none}"
fi

# --- 1) Stop and disable services (in reverse dep order) ---
for svc in "${SERVICES[@]}"; do
  if systemctl list-unit-files | grep -q "^${svc}"; then
    echo "--- Stopping ${svc} ---"
    systemctl stop "${svc}" || true
    echo "--- Disabling ${svc} ---"
    systemctl disable "${svc}" || true
  else
    echo "NOTE: ${svc} not found (skipping stop/disable)."
  fi
done

# --- 2) Remove unit files ---
for svc in "${SERVICES[@]}"; do
  if [[ -f "${SYSTEMD_DIR}/${svc}" ]]; then
    echo "--- Removing unit: ${svc} ---"
    rm -f "${SYSTEMD_DIR}/${svc}"
  fi
done

echo "--- Reloading systemd ---"
systemctl daemon-reload
systemctl reset-failed || true

# --- 3) Remove app directory ---
if [[ -d "${STREAM_DIR}" ]]; then
  echo "--- Removing ${STREAM_DIR} ---"
  rm -rf "${STREAM_DIR}"
else
  echo "NOTE: ${STREAM_DIR} not found."
fi

# --- 4) (Optional) Clean pip cache for this user ---
echo "--- Cleaning pip cache (optional) ---"
sudo -u "${TARGET_USER}" bash -c "pip cache purge" || true

echo
echo "✅ Streaming_HID stack removed."
echo "Verify with:"
echo "  systemctl list-units | grep -E 'streaming_hid|start_streaming|composite-gadget' || echo 'no units found'"
echo "  ls -la ${TARGET_HOME}"
