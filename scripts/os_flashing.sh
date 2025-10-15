#!/usr/bin/env bash
# ---------------------------------------------------------
# rpi_bootstrap_os_flashing.sh
# Installs and configures OS_Flashing directly in /home/rpi
# with auto service setup (sparse checkout version)
# ---------------------------------------------------------
set -euo pipefail

### --- CONFIG --- ###
GIT_REPO="${1:-https://github.com/Rutomatrix/Intel-features}"
BRANCH="${2:-main}"
SERVICE_NAME="usb_mass_storage.service"
TARGET_USER="${SUDO_USER:-rpi}"
TARGET_HOME="/home/${TARGET_USER}"
OS_DIR="${TARGET_HOME}/OS_Flashing"
VENV_DIR="${OS_DIR}/venv"
PYTHON_BIN="${VENV_DIR}/bin/python"
SYSTEMD_PATH="/etc/systemd/system/${SERVICE_NAME}"
REQUIREMENTS_FILE="${OS_DIR}/requirements.txt"
TMP_SERVICE="/tmp/${SERVICE_NAME}"

if [[ -z "${GIT_REPO}" ]]; then
  echo "Usage: sudo $0 <git_repo_url> [branch]"
  exit 2
fi

echo "=== Starting OS_Flashing setup ==="
echo "Repo: ${GIT_REPO}"
echo "Branch: ${BRANCH}"
echo "Target dir: ${OS_DIR}"
echo

# --- 1) Install dependencies ---
echo "--- Installing dependencies ---"
apt-get update -y
apt-get install -y git python3 python3-venv python3-pip

# --- 2) Sparse clone only OS_Flashing folder ---
TMP_CLONE="/tmp/osflashing_repo"
rm -rf "${TMP_CLONE}"
mkdir -p "${TMP_CLONE}"
cd "${TMP_CLONE}"

echo "--- Performing sparse checkout of OS_Flashing ---"
git init
git remote add origin "${GIT_REPO}"
git fetch --depth 1 origin "${BRANCH}"
git sparse-checkout init --cone
git sparse-checkout set "OS_Flashing"
git checkout "${BRANCH}"

# --- 3) Copy OS_Flashing directory to target ---
if [[ ! -d "${TMP_CLONE}/OS_Flashing" ]]; then
  echo "ERROR: OS_Flashing folder not found in the repo!"
  exit 3
fi

echo "--- Copying OS_Flashing to ${TARGET_HOME} ---"
rm -rf "${OS_DIR}"
cp -r "${TMP_CLONE}/OS_Flashing" "${OS_DIR}"
chown -R "${TARGET_USER}:${TARGET_USER}" "${OS_DIR}"

# --- 4) Setup Python virtual environment ---
if [[ ! -d "${VENV_DIR}" ]]; then
  echo "Creating venv..."
  python3 -m venv "${VENV_DIR}"
fi

echo "Installing dependencies from requirements.txt..."
"${VENV_DIR}/bin/pip" install --upgrade pip setuptools wheel
if [[ -f "${REQUIREMENTS_FILE}" ]]; then
  "${VENV_DIR}/bin/pip" install -r "${REQUIREMENTS_FILE}"
else
  echo "No requirements.txt found. Installing default Flask..."
  "${VENV_DIR}/bin/pip" install flask
fi

# --- 5) Ensure templates/index.html exists ---
mkdir -p "${OS_DIR}/templates"
if [[ ! -f "${OS_DIR}/templates/index.html" ]]; then
  echo "Creating sample index.html..."
  cat > "${OS_DIR}/templates/index.html" <<'HTML'
<!doctype html>
<html>
  <head><meta charset="utf-8"><title>OS Flashing</title></head>
  <body><h1>OS Flashing - Local Test Page</h1></body>
</html>
HTML
fi

# --- 5.5) Ensure /home/rpi/os directory exists ---
OS_DATA_DIR="${TARGET_HOME}/os"
if [[ ! -d "${OS_DATA_DIR}" ]]; then
  echo "Creating directory ${OS_DATA_DIR}..."
  mkdir -p "${OS_DATA_DIR}"
  chown -R "${TARGET_USER}:${TARGET_USER}" "${OS_DATA_DIR}"
fi

# --- 6) Setup systemd service ---
SERVICE_SRC="${TMP_CLONE}/OS_Flashing/${SERVICE_NAME}"
if [[ ! -f "${SERVICE_SRC}" ]]; then
  echo "No ${SERVICE_NAME} found in repo — creating one."
  cat > "${TMP_SERVICE}" <<SERVICE
[Unit]
Description=USB Mass Storage OS Flashing Service
After=network.target

[Service]
User=root
WorkingDirectory=${OS_DIR}
ExecStart=${PYTHON_BIN} ${OS_DIR}/app.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
SERVICE
else
  echo "Patching ExecStart in service file..."
  sed "s|ExecStart=.*|ExecStart=${PYTHON_BIN} ${OS_DIR}/app.py|" "${SERVICE_SRC}" > "${TMP_SERVICE}"
fi

cp "${TMP_SERVICE}" "${SYSTEMD_PATH}"
chmod 644 "${SYSTEMD_PATH}"

# --- 7) Enable and start the service ---
echo "--- Enabling and starting ${SERVICE_NAME} ---"
systemctl daemon-reload
systemctl enable --now "${SERVICE_NAME}"

echo
echo "✅ OS_Flashing installed successfully!"
echo "To check status:   sudo systemctl status ${SERVICE_NAME}"
echo "To view logs:      sudo journalctl -u ${SERVICE_NAME} -f"
echo "To test endpoint:  curl http://127.0.0.1:9001/"
