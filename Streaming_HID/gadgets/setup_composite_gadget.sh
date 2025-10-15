#!/bin/bash

GADGET=/sys/kernel/config/usb_gadget/composite_gadget
ISO_FILE=""

# Clean existing gadget
if [ -d "$GADGET" ]; then
    echo "" > "$GADGET/UDC" 2>/dev/null || true
    sleep 1
    rm -f "$GADGET/configs/c.1/"*
    rm -rf "$GADGET/functions/"*
    rm -rf "$GADGET/strings/0x409"
    rm -rf "$GADGET/configs/c.1/strings/0x409"
    rmdir "$GADGET" 2>/dev/null || true
    sleep 1
fi

modprobe libcomposite
mkdir -p "$GADGET"
cd "$GADGET"

# IDs
echo 0x1d6b > idVendor
echo 0x0104 > idProduct
echo 0x0100 > bcdDevice
echo 0x0200 > bcdUSB

# Strings
mkdir -p strings/0x409
echo "0123456789" > strings/0x409/serialnumber
echo "RPi Composite" > strings/0x409/product
echo "Raspberry Pi" > strings/0x409/manufacturer

# Configs
mkdir -p configs/c.1/strings/0x409
echo "HID + Storage" > configs/c.1/strings/0x409/configuration
echo 120 > configs/c.1/MaxPower

# HID Keyboard
mkdir -p functions/hid.usb0
echo 1 > functions/hid.usb0/protocol
echo 1 > functions/hid.usb0/subclass
echo 8 > functions/hid.usb0/report_length
echo -ne '\x05\x01\x09\x06\xa1\x01\x05\x07\x19\xe0\x29\xe7\x15\x00\x25\x01\x75\x01\x95\x08\x81\x02\x95\x01\x75\x08\x81\x01\x95\x05\x75\x01\x05\x08\x19\x01\x29\x05\x91\x02\x95\x01\x75\x03\x91\x01\x95\x06\x75\x08\x15\x00\x25\x65\x05\x07\x19\x00\x29\x65\x81\x00\xc0' > functions/hid.usb0/report_desc
# HID Mouse
mkdir -p functions/hid.usb1
echo 2 > functions/hid.usb1/protocol
echo 1 > functions/hid.usb1/subclass
echo 3 > functions/hid.usb1/report_length
echo -ne '\x05\x01\x09\x02\xa1\x01\x09\x01\xa1\x00\x05\x09\x19\x01\x29\x03\x15\x00\x25\x01\x95\x03\x75\x01\x81\x02\x95\x01\x75\x05\x81\x01\x05\x01\x09\x30\x09\x31\x15\x81\x25\x7f\x75\x08\x95\x02\x81\x06\xc0\xc0' > functions/hid.usb1/report_desc
# Mass Storage (no ISO yet)
mkdir -p functions/mass_storage.usb0
echo 1 > functions/mass_storage.usb0/stall
echo 0 > functions/mass_storage.usb0/lun.0/removable
echo 1 > functions/mass_storage.usb0/lun.0/ro
echo "" > functions/mass_storage.usb0/lun.0/file  # Empty for now

# Link functions
ln -s functions/hid.usb0 configs/c.1/
ln -s functions/hid.usb1 configs/c.1/
ln -s functions/mass_storage.usb0 configs/c.1/

# Bind
UDC=$(ls /sys/class/udc | head -n1)
echo "$UDC" > UDC

echo "✅ Composite gadget (HID + Storage) is set up!"