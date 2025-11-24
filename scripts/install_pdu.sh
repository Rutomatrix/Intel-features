#!/usr/bin/env bash
# ---------------------------------------------------------
# install_pdu.sh
# Installs and configures the PDU app to /home/rpi/PDU
# and sets up/starts a systemd service: pdu.service
# ---------------------------------------------------------
set -euo pipefail

### --- CONFIG --- ###
GIT_REPO="${1:-https://github.com/Rutomatrix/Intel-features}"
BRANCH="${2:-main}"
TARGET_USER="${SUDO_USER:-rpi}"
TARGET_HOME="/home/${TARGET_USER}"
APP_DIR="${TARGET_HOME}/PDU"
TMP_CLONE="/tmp/pdu_repo"
VENV_DIR="${APP_DIR}/venv"
SYSTEMD_DIR="/etc/systemd/system"
SERVICE_NAME="pdu.service"

echo "=== Installing PDU app ==="
echo "Repo:    ${GIT_REPO}"
echo "Branch:  ${BRANCH}"
echo "Target:  ${APP_DIR}"
echo

# 1) Base deps
echo "--- Installing dependencies ---"
apt-get update -y
apt-get install -y git python3 python3-venv python3-pip

# 2) Sparse checkout of PDU/
echo "--- Sparse-cloning PDU/ ---"
rm -rf "${TMP_CLONE}"
mkdir -p "${TMP_CLONE}"
git -C "${TMP_CLONE}" init
git -C "${TMP_CLONE}" remote add origin "${GIT_REPO}"
git -C "${TMP_CLONE}" fetch --depth 1 origin "${BRANCH}"
git -C "${TMP_CLONE}" sparse-checkout init --cone
git -C "${TMP_CLONE}" sparse-checkout set "PDU"
git -C "${TMP_CLONE}" checkout "${BRANCH}"

# 3) Copy into place (fresh)
echo "--- Deploying to ${APP_DIR} ---"
rm -rf "${APP_DIR}"
cp -r "${TMP_CLONE}/PDU" "${APP_DIR}"
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

# 5) Ensure web assets (templates/, static/) are present
echo "--- Ensuring web assets (templates/, static/) ---"

SRC_DIR="${TMP_CLONE}/PDU"

# If repo has templates/ but target doesn't (shouldn't happen, but be safe)
if [[ -d "${SRC_DIR}/templates" && ! -d "${APP_DIR}/templates" ]]; then
  echo "Copying templates/ from repo..."
  cp -r "${SRC_DIR}/templates" "${APP_DIR}/templates"
fi

# If repo has static/ but target doesn't
if [[ -d "${SRC_DIR}/static" && ! -d "${APP_DIR}/static" ]]; then
  echo "Copying static/ from repo..."
  cp -r "${SRC_DIR}/static" "${APP_DIR}/static"
fi

# Fallback: if no templates folder but a root index.html exists, move it in
if [[ ! -d "${APP_DIR}/templates" && -f "${APP_DIR}/index.html" ]]; then
  echo "templates/ missing but index.html found — moving to templates/"
  mkdir -p "${APP_DIR}/templates"
  mv "${APP_DIR}/index.html" "${APP_DIR}/templates/index.html"
fi

# Fix ownership
chown -R "${TARGET_USER}:${TARGET_USER}" "${APP_DIR}"


# 6) Write systemd service
SERVICE_PATH="${SYSTEMD_DIR}/${SERVICE_NAME}"
echo "--- Installing systemd service: ${SERVICE_PATH} ---"
cat > "${SERVICE_PATH}" <<EOF
[Unit]
Description=PDU Service
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
echo "✅ PDU installed!"
echo "Status:  sudo systemctl status ${SERVICE_NAME}"
echo "Logs:    sudo journalctl -u ${SERVICE_NAME} -f"
