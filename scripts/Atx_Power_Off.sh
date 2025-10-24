#!/bin/bash
# ATX Power Off (simulate pressing the power button)

# Step 1: Select I2C Mux Channel 1 (same as reset)
i2cset -y 1 0x72 0x00 0x02

# Step 2: Set GPIO direction (0x3f = lower 6 bits input, upper 2 bits output)
i2cset -y 1 0x24 0x00 0x3f

# Step 3: Set Config Register (if needed, sets polarity) — optional
i2cset -y 1 0x24 0x0c 0xc0

# Step 4: Press the power button (bit 7 high = 0x80)
i2cset -y 1 0x24 0x12 0x80
sleep 3

# Step 5: Release the power button (bit 7 low = 0x00)
i2cset -y 1 0x24 0x12 0x00
