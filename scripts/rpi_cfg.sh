#!/usr/bin/env bash
# ---------------------------------------------------------
# rpi_cfg.sh
# One-shot Raspberry Pi configuration:
#   • Replace firmware config.txt (default: /home/<user>/config.txt)
#   • Enable UART and serial login shell
#   • Reboot (unless --no-reboot)
#
# Works with NO ARGS out of the box.
# ---------------------------------------------------------
set -euo pipefail

# ---- Defaults (no-arg behavior) ----
TARGET_USER="${SUDO_USER:-rpi}"
HOME_DIR="/home/${TARGET_USER}"
DEFAULT_CONFIG="${HOME_DIR}/config.txt"   # default source if --config-file not given

CONFIG_FILE=""          # override via --config-file
NO_REBOOT=0             # --no-reboot to skip reboot
LOGIN_SHELL=1           # default ON; use --no-login-shell to turn off

usage() {
  cat <<EOF
Usage: sudo ./rpi_cfg.sh [--config-file /path/to/config.txt] [--no-reboot] [--no-login-shell]

Defaults (no args):
  • Replace with ${DEFAULT_CONFIG} if present
  • Enable UART and serial login shell
  • Reboot

Options:
  --config-file PATH   Use a specific replacement for firmware config.txt
  --no-reboot          Apply changes but do not reboot
  --no-login-shell     Do NOT enable serial login shell (UART stays enabled)
  -h, --help           Show this help
EOF
}

# ---- Parse args ----
while [[ $# -gt 0 ]]; do
  case "$1" in
    --config-file) CONFIG_FILE="${2:-}"; shift 2 ;;
    --no-reboot)   NO_REBOOT=1; shift ;;
    --no-login-shell) LOGIN_SHELL=0; shift ;;
    -h|--help)     usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 2 ;;
  esac
done

# ---- Must be root ----
if [[ "${EUID}" -ne 0 ]]; then
  echo "Please run as root (use: sudo $0 ...)"
  exit 1
fi

# ---- Resolve source config.txt ----
SRC_CFG="${CONFIG_FILE:-}"
if [[ -z "${SRC_CFG}" ]]; then
  if [[ -f "${DEFAULT_CONFIG}" ]]; then
    SRC_CFG="${DEFAULT_CONFIG}"
  else
    echo "ERROR: No --config-file given and default ${DEFAULT_CONFIG} not found." >&2
    exit 3
  fi
fi
if [[ ! -f "${SRC_CFG}" ]]; then
  echo "ERROR: Source config not found: ${SRC_CFG}" >&2
  exit 4
fi

# ---- Locate firmware config.txt destination ----
FW_DIR="/boot/firmware"
ALT_DIR="/boot"
CFG_PATH=""
if [[ -f "${FW_DIR}/config.txt" ]]; then
  CFG_PATH="${FW_DIR}/config.txt"
elif [[ -f "${ALT_DIR}/config.txt" ]]; then
  CFG_PATH="${ALT_DIR}/config.txt"
else
  echo "ERROR: firmware config.txt not found in ${FW_DIR} or ${ALT_DIR}" >&2
  exit 5
fi

STAMP="$(date +'%Y%m%d-%H%M%S')"
backup_file() {
  local f="$1"
  if [[ -f "$f" ]]; then
    cp -a "$f" "${f}.bak.${STAMP}"
    echo "Backup created: ${f}.bak.${STAMP}"
  fi
}

ensure_kv() {
  local key="$1" val="$2"
  if grep -qE "^[[:space:]]*${key}=" "${CFG_PATH}"; then
    sed -i "s|^[[:space:]]*${key}=.*|${key}=${val}|" "${CFG_PATH}"
  else
    echo "${key}=${val}" >> "${CFG_PATH}"
  fi
}

echo "=== rpi_cfg: start ==="
echo "Using source: ${SRC_CFG}"
echo "Firmware config: ${CFG_PATH}"

# 1) Replace firmware config.txt (with backup)
echo "--- Replacing firmware config.txt ---"
backup_file "${CFG_PATH}"
install -m 0644 "${SRC_CFG}" "${CFG_PATH}"

# 2) Ensure UART enabled (even if file already had it)
echo "--- Enabling UART (enable_uart=1) ---"
ensure_kv "enable_uart" "1"
sync

# 3) Serial login shell (serial-getty) enable/disable
if [[ "${LOGIN_SHELL}" -eq 1 ]]; then
  echo "--- Enabling serial login shell ---"
  if [[ -e /dev/ttyAMA0 ]]; then
    systemctl enable --now serial-getty@ttyAMA0.service || true
  elif [[ -e /dev/ttyS0 ]]; then
    systemctl enable --now serial-getty@ttyS0.service || true
  else
    echo "WARN: No /dev/ttyAMA0 or /dev/ttyS0 detected; skipping serial-getty."
  fi
else
  echo "--- Leaving serial login shell OFF ---"
fi

echo "=== rpi_cfg: complete ==="
if [[ "${NO_REBOOT}" -eq 0 ]]; then
  echo "Rebooting now..."
  sync
  systemctl reboot
else
  echo "NO_REBOOT=1 set; skipping reboot."
fi
