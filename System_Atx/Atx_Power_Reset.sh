#!/bin/bash

# Set direction again to be safe
i2cset -y 1 0x24 0x00 0x3f

# Read current output state
current=$(i2cget -y 1 0x24 0x12)
# Set Bit 6 (reset)
newval=$((current | 0x40))
i2cset -y 1 0x24 0x12 $newval
sleep 1
# Clear Bit 6 (reset release)
newval=$((current & 0xBF))
i2cset -y 1 0x24 0x12 $newval
