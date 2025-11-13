#!/bin/bash
set -e

# --- CONFIG ---
MARKER_FILE="/tmp/flashrom_spi_stage"
CONFIG_FILE="/boot/config.txt"
MODULES_FILE="/etc/modules-load.d/raspberrypi.conf"

# --- FUNCTION DEFINITIONS ---
function stage1() {
    echo "========== Stage 1: Checking flashrom version =========="
    if ! command -v flashrom &> /dev/null; then
        echo "flashrom not found. Installing..."
        sudo apt update -y
        sudo apt install -y flashrom
    else
        flashrom --version
    fi

    echo "========== Stage 2: Updating /boot/config.txt =========="
    if grep -q "^#dtparam=spi=on" "$CONFIG_FILE"; then
        echo "Uncommenting dtparam=spi=on..."
        sudo sed -i 's/^#dtparam=spi=on/dtparam=spi=on/' "$CONFIG_FILE"
    elif ! grep -q "dtparam=spi=on" "$CONFIG_FILE"; then
        echo "Adding dtparam=spi=on..."
        echo "dtparam=spi=on" | sudo tee -a "$CONFIG_FILE" > /dev/null
    else
        echo "dtparam=spi=on already enabled."
    fi

    echo "========== Stage 3: Rebooting to apply SPI config =========="
    echo "2" | sudo tee "$MARKER_FILE" > /dev/null
    sudo reboot
}

function stage2() {
    echo "========== Stage 4: Checking SPI module =========="
    if lsmod | grep -q spi; then
        echo "SPI module already loaded."
    else
        echo "SPI module not yet loaded — continuing anyway."
    fi

    echo "========== Stage 5: Checking /etc/modules-load.d/raspberrypi.conf =========="
    if [ ! -f "$MODULES_FILE" ]; then
        echo "Creating $MODULES_FILE..."
        echo "spi-dev" | sudo tee "$MODULES_FILE" > /dev/null
    else
        if grep -q "^#spi-dev" "$MODULES_FILE"; then
            echo "Uncommenting spi-dev..."
            sudo sed -i 's/^#spi-dev/spi-dev/' "$MODULES_FILE"
        elif ! grep -q "spi-dev" "$MODULES_FILE"; then
            echo "Adding spi-dev..."
            echo "spi-dev" | sudo tee -a "$MODULES_FILE" > /dev/null
        else
            echo "spi-dev already enabled."
        fi
    fi

    echo "========== Stage 6: Rebooting to load spi-dev module =========="
    echo "3" | sudo tee "$MARKER_FILE" > /dev/null
    sudo reboot
}

function stage3() {
    echo "========== Final Stage: Verifying SPI status =========="
    lsmod | grep spi || echo "Warning: SPI module not detected yet."
    echo "SPI setup completed successfully ✅"
    sudo rm -f "$MARKER_FILE"
}

# --- MAIN EXECUTION LOGIC ---
STAGE=$(cat "$MARKER_FILE" 2>/dev/null || echo "1")

case "$STAGE" in
    "1")
        stage1
        ;;
    "2")
        stage2
        ;;
    "3")
        stage3
        ;;
    *)
        echo "Invalid stage marker. Starting from scratch..."
        sudo rm -f "$MARKER_FILE"
        stage1
        ;;
esac
