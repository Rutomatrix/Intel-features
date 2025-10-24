#!/bin/bash

I2C_MUX_ADDR=0x72
MUX_SEL_BYTE=0x02
I2C_ADDR=0x24
INPUT_REG=0x12
DIR_REG=0x00
CONF_REG=0x0C

select_mux() {
    i2cset -y 1 $I2C_MUX_ADDR 0x00 $MUX_SEL_BYTE &>/dev/null
}

init_expander() {
    # lower 6 bits as inputs, upper 2 bits don't care
    i2cset -y 1 $I2C_ADDR $DIR_REG 0x3f &>/dev/null
    # polarity/config (all inputs normal)
    i2cset -y 1 $I2C_ADDR $CONF_REG 0xff &>/dev/null
}

read_state() {
    local hexv decv masked bin6
    hexv=$(i2cget -y 1 $I2C_ADDR $INPUT_REG 2>/dev/null) || { echo "Read error"; return; }
    hexv=${hexv#0x}
    decv=$((16#$hexv))
    # mask to lower 6 bits only
    masked=$(( decv & 0x3F ))
    # 6-bit binary string
    bin6=$(printf "%06d" "$(echo "obase=2; $masked" | bc)")

    # clear the inputs for next event
    i2cset -y 1 $I2C_ADDR $INPUT_REG 0x00 &>/dev/null

    case "$bin6" in
        111111) echo "server off"   ;;  # 0x3F
        110111) echo "shutdown"     ;;  # 0x37
        110110) echo "hybernate"    ;;  # 0x36
        110000) echo "active"       ;;  # 0x30
        *)      echo "Unknown: $bin6" ;;
    esac
}

while true; do
    select_mux
    init_expander
    read_state
    sleep 2
done
