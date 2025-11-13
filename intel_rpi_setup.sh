#!/bin/bash

set -e  # Exit immediately if a command fails

REPO_URL="https://github.com/Rutomatrix/Intel-features.git"
INSTALL_DIR="/home/rpi/Intel-features"
SYSTEMD_DIR="/etc/systemd/system"

echo "=========================================="
echo "🔍 Step 1: Checking if git is installed..."
echo "=========================================="
if ! command -v git &> /dev/null; then
    echo "❌ Git not found. Installing git..."
    sudo apt update -y
    sudo apt install git -y
else
    echo "✅ Git is already installed."
fi

echo "=========================================="
echo "📦 Step 2: Cloning repository..."
echo "=========================================="
if [ -d "$INSTALL_DIR" ]; then
    echo "📁 Repository already exists. Pulling latest changes..."
    cd "$INSTALL_DIR"
    git pull
else
    echo "📥 Cloning into $INSTALL_DIR..."
    git clone "$REPO_URL" "$INSTALL_DIR"
fi

echo "=========================================="
echo "⚙️ Step 3: Moving service files..."
echo "=========================================="
cd "$INSTALL_DIR"
if [ -d "service files" ]; then
    echo "📤 Copying service files to $SYSTEMD_DIR..."
    sudo cp -v "service files"/* "$SYSTEMD_DIR"/
else
    echo "❌ 'service files' folder not found!"
    exit 1
fi

echo "=========================================="
echo "🔒 Step 4: Making all bash files executable..."
echo "=========================================="
find "$INSTALL_DIR" -type f -name "*.sh" -exec chmod +x {} \;
echo "✅ All .sh files are now executable."

echo "=========================================="
echo "🚀 Step 5: Running dependency scripts..."
echo "=========================================="
if [ -d "$INSTALL_DIR/dependencies" ]; then
    for script in "$INSTALL_DIR"/dependencies/*.sh; do
        echo "▶️ Running dependency: $script"
        bash "$script"
    done
else
    echo "⚠️ No dependencies folder found. Skipping..."
fi

echo "=========================================="
echo "🧩 Step 6: Running config scripts..."
echo "=========================================="
if [ -d "$INSTALL_DIR/configs" ]; then
    for script in "$INSTALL_DIR"/configs/*.sh; do
        echo "▶️ Running config: $script"
        bash "$script"
    done
else
    echo "⚠️ No configs folder found. Skipping..."
fi

echo "=========================================="
echo "🧠 Step 7: Enabling and starting service files..."
echo "=========================================="
for service_file in "$SYSTEMD_DIR"/*.service; do
    if grep -q "Rutomatrix" "$service_file" 2>/dev/null; then
        service_name=$(basename "$service_file")
        echo "🔧 Enabling and starting $service_name..."
        sudo systemctl daemon-reload
        sudo systemctl enable "$service_name"
        sudo systemctl start "$service_name" || {
            echo "⚠️ Failed to start $service_name. Might need a reboot."
            NEED_REBOOT=true
        }
    fi
done

if [ "$NEED_REBOOT" = true ]; then
    echo "🔁 Reboot required. Rebooting now..."
    sudo reboot
else
    echo "✅ All services are enabled and running."
fi

echo "=========================================="
echo "🎉 Setup completed successfully!"
echo "=========================================="
