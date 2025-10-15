#!/usr/bin/env bash
# ---------------------------------------------------------
# rpi_bootstrap_streaming_hid.sh
# Installs and configures Streaming_HID directly in /home/rpi
# with auto service setup for:
#   - composite-gadget.service
#   - start_streaming.service
#   - streaming_hid.service
# ---------------------------------------------------------
set -euo pipefail

### --- CONFIG --- ###
GIT_REPO="${1:-https://github.com/Rutomatrix/Intel-features}"
BRANCH="${2:-main}"
TARGET_USER="${SUDO_USER:-rpi}"
TARGET_HOME="/home/${TARGET_USER}"
STREAM_DIR="${TARGET_HOME}/Streaming_HID"
VENV_DIR="${STREAM_DIR}/venv"
PYTHON_BIN="${VENV_DIR}/bin/python"
TMP_CLONE="/tmp/streaminghid_repo"
SYSTEMD_DIR="/etc/systemd/system"

SERVICES=(
  "composite-gadget.service"
  "start_streaming.service"
  "streaming_hid.service"
)

echo "=== Starting Streaming_HID setup ==="
echo "Repo: ${GIT_REPO}"
echo "Branch: ${BRANCH}"
echo "Target dir: ${STREAM_DIR}"
echo

# --- 1) Install dependencies ---
echo "--- Installing dependencies ---"
apt-get update -y
apt-get install -y git python3 python3-venv python3-pip

# --- 2) Sparse clone only Streaming_HID folder ---
rm -rf "${TMP_CLONE}"
mkdir -p "${TMP_CLONE}"
cd "${TMP_CLONE}"

echo "--- Performing sparse checkout of Streaming_HID ---"
git init
git remote add origin "${GIT_REPO}"
git fetch --depth 1 origin "${BRANCH}"
git sparse-checkout init --cone
git sparse-checkout set "Streaming_HID"
git checkout "${BRANCH}"

# --- 3) Copy Streaming_HID to target ---
if [[ ! -d "${TMP_CLONE}/Streaming_HID" ]]; then
  echo "ERROR: Streaming_HID folder not found in the repo!"
  exit 3
fi

echo "--- Copying Streaming_HID to ${TARGET_HOME} ---"
rm -rf "${STREAM_DIR}"
cp -r "${TMP_CLONE}/Streaming_HID" "${STREAM_DIR}"
chown -R "${TARGET_USER}:${TARGET_USER}" "${STREAM_DIR}"


# --- 4) Setup Python virtual environment ---
if [[ ! -d "${VENV_DIR}" ]]; then
  echo "Creating venv..."
  python3 -m venv "${VENV_DIR}"
fi

echo "Installing dependencies from requirements.txt..."
"${VENV_DIR}/bin/pip" install --upgrade pip setuptools wheel
if [[ -f "${STREAM_DIR}/requirements.txt" ]]; then
  "${VENV_DIR}/bin/pip" install -r "${STREAM_DIR}/requirements.txt"
else
  echo "No requirements.txt found. Installing FastAPI & Uvicorn..."
  "${VENV_DIR}/bin/pip" install fastapi uvicorn
fi

# --- 4.1) Build & install ustreamer inside Streaming_HID ---
install_ustreamer_in_tree() {
  echo "--- Installing build deps for ustreamer ---"
  apt-get install -y \
    build-essential \
    libevent-dev \
    libjpeg-dev \
    libbsd-dev \
    libv4l-dev \
    git \
    pkg-config

  USTREAMER_SRC="${STREAM_DIR}/ustreamer"

  # Always remove any pre-copied (empty/stale) ustreamer dir from repo
  if [[ -d "${USTREAMER_SRC}" ]]; then
    echo "--- Removing bundled ${USTREAMER_SRC} ---"
    rm -rf "${USTREAMER_SRC}"
  fi

  echo "--- Cloning ustreamer into ${USTREAMER_SRC} ---"
  git clone --depth 1 https://github.com/pikvm/ustreamer.git "${USTREAMER_SRC}"
  chown -R "${TARGET_USER}:${TARGET_USER}" "${USTREAMER_SRC}"

  echo "--- Verifying Makefile ---"
  if [[ ! -f "${USTREAMER_SRC}/Makefile" ]]; then
    echo "ERROR: Makefile not found in ${USTREAMER_SRC}"
    ls -la "${USTREAMER_SRC}"
    exit 12
  fi

  echo "--- Building ustreamer ---"
  make -C "${USTREAMER_SRC}" -j"$(nproc)"

  echo "--- Installing ustreamer to /usr/local/bin ---"
  make -C "${USTREAMER_SRC}" install
  ldconfig || true

  if ! command -v ustreamer >/dev/null 2>&1; then
    echo "ERROR: ustreamer not found after install."
    exit 13
  fi
  echo "✅ ustreamer installed."
}

install_ustreamer_in_tree




# --- 5) Install and enable systemd services ---
echo "--- Installing and enabling systemd services ---"
for svc in "${SERVICES[@]}"; do
  SRC_PATH="${STREAM_DIR}/${svc}"
  DEST_PATH="${SYSTEMD_DIR}/${svc}"

  if [[ -f "${SRC_PATH}" ]]; then
    echo "Installing ${svc}..."
    cp "${SRC_PATH}" "${DEST_PATH}"
    chmod 644 "${DEST_PATH}"
  else
    echo "WARNING: ${svc} not found in repo."
  fi
done

# Reload and enable all services
systemctl daemon-reload
for svc in "${SERVICES[@]}"; do
  if [[ -f "${SYSTEMD_DIR}/${svc}" ]]; then
    echo "Enabling and starting ${svc}..."
    systemctl enable --now "${svc}" || echo "⚠️ Failed to start ${svc}"
  fi
done

echo
echo "✅ Streaming_HID installed successfully!"
echo "Check status with:   sudo systemctl status start_streaming.service"
echo "To view logs:        sudo journalctl -u start_streaming.service -f"
echo "All services:        sudo systemctl list-units | grep streaming"
