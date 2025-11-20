#!/usr/bin/env bash
# ---------------------------------------------------------
# postcode.sh
# Installs and configures the Postcode Flask app to /home/rpi/Postcode
# and sets up/starts a systemd service: postcode.service
# ---------------------------------------------------------
set -euo pipefail

### --- CONFIG --- ###
GIT_REPO="${1:-https://github.com/Rutomatrix/Intel-features}"
BRANCH="${2:-main}"
TARGET_USER="${SUDO_USER:-rpi}"
TARGET_HOME="/home/${TARGET_USER}"
APP_DIR="${TARGET_HOME}/Postcode"
TMP_CLONE="/tmp/postcode_repo"
VENV_DIR="${APP_DIR}/venv"
SYSTEMD_DIR="/etc/systemd/system"
SERVICE_NAME="postcode.service"

echo "=== Installing Postcode app ==="
echo "Repo:    ${GIT_REPO}"
echo "Branch:  ${BRANCH}"
echo "Target:  ${APP_DIR}"
echo

# 0) Disable/stop hciuart FIRST (Bluetooth UART daemon can occupy UART)
echo "--- Disabling and stopping hciuart ---"
systemctl disable hciuart || true
systemctl stop hciuart || true

# 1) Base deps
echo "--- Installing dependencies ---"
apt-get update -y
apt-get install -y git python3 python3-venv python3-pip

# 2) Sparse checkout of Postcode/
echo "--- Sparse-cloning Postcode/ ---"
rm -rf "${TMP_CLONE}"
mkdir -p "${TMP_CLONE}"
git -C "${TMP_CLONE}" init
git -C "${TMP_CLONE}" remote add origin "${GIT_REPO}"
git -C "${TMP_CLONE}" fetch --depth 1 origin "${BRANCH}"
git -C "${TMP_CLONE}" sparse-checkout init --cone
git -C "${TMP_CLONE}" sparse-checkout set "Postcode"
git -C "${TMP_CLONE}" checkout "${BRANCH}"

# 3) Copy into place (fresh)
echo "--- Deploying to ${APP_DIR} ---"
rm -rf "${APP_DIR}"
cp -r "${TMP_CLONE}/Postcode" "${APP_DIR}"
chown -R "${TARGET_USER}:${TARGET_USER}" "${APP_DIR}"

# 4) Create venv + install requirements
echo "--- Creating virtualenv ---"
python3 -m venv "${VENV_DIR}"
"${VENV_DIR}/bin/pip" install --upgrade pip setuptools wheel

REQ_FILE="${APP_DIR}/requirements.txt"
if [[ -f "${REQ_FILE}" ]]; then
  echo "--- Installing requirements.txt ---"
  "${VENV_DIR}/bin/pip" install -r "${REQ_FILE}"
else
  echo "WARNING: requirements.txt not found; installing basics (Flask, CORS, pyserial)"
  "${VENV_DIR}/bin/pip" install flask flask-cors pyserial
fi

# 5) Ensure templates/index.html exists (Flask uses templates/)
echo "--- Ensuring templates/index.html ---"
mkdir -p "${APP_DIR}/templates"
if [[ -f "${APP_DIR}/index.html" && ! -f "${APP_DIR}/templates/index.html" ]]; then
  mv "${APP_DIR}/index.html" "${APP_DIR}/templates/index.html"
fi
chown -R "${TARGET_USER}:${TARGET_USER}" "${APP_DIR}"

# 6) Write systemd service (if not already shipped in repo)
SERVICE_PATH="${SYSTEMD_DIR}/${SERVICE_NAME}"
echo "--- Installing systemd service: ${SERVICE_PATH} ---"
cat > "${SERVICE_PATH}" <<EOF
[Unit]
Description=Postcode Flask Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${TARGET_USER}
WorkingDirectory=${APP_DIR}
Environment=PYTHONUNBUFFERED=1
ExecStart=${VENV_DIR}/bin/python ${APP_DIR}/app.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

chmod 0644 "${SERVICE_PATH}"

# 7) Enable + start
echo "--- Enabling and starting ${SERVICE_NAME} ---"
systemctl daemon-reload
systemctl enable --now "${SERVICE_NAME}"

echo
echo "✅ Postcode installed!"
echo "Status:  sudo systemctl status ${SERVICE_NAME} -n 50"
echo "Logs:    sudo journalctl -u ${SERVICE_NAME} -f"
