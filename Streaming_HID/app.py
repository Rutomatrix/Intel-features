from flask import Flask, request, render_template
from flask_cors import CORS
import subprocess
import socket
import os
import signal
import time
import re

app = Flask(__name__)
# Allow all origins (for development)
CORS(app)

KEYBOARD_PATH = "/dev/hidg0"
MOUSE_PATH = "/dev/hidg1"

import subprocess
import re

# -----------------------------
# Get USB capture devices and their paths
# -----------------------------
result = subprocess.run(["v4l2-ctl", "--list-devices"], capture_output=True, text=True)
output = result.stdout

devices = output.strip().split("\n\n")
hub_port_mapping = {}  # map USB path to /dev/videoX

for block in devices:
    lines = block.splitlines()
    if len(lines) < 2:
        continue

    device_name = lines[0]
    if "usb" in device_name.lower():  # consider USB devices only
        # USB path is inside parentheses
        match = re.search(r"\((usb[^\)]+)\)", device_name)
        if match:
            usb_path = match.group(1)
            # Collect all /dev/video* lines in this block
            video_lines = [line.strip() for line in lines[1:] if line.strip().startswith("/dev/video")]
            if video_lines:
                # Pick the lowest numbered /dev/video device
                hub_port_mapping[usb_path] = sorted(video_lines, key=lambda x: int(x.replace("/dev/video","")))[0]

# -----------------------------
# Select the device for the first hub port or fallback
# -----------------------------
usb_video = hub_port_mapping.get("usb-0000:01:00.0-1.1.1")  # first hub port

# Fallback: if first hub port doesn't exist (single capture connected directly)
if not usb_video and hub_port_mapping:
    usb_video = list(hub_port_mapping.values())[0]

print(f"Virtual Desk video device: {usb_video}")


USTREAMER_CMD = [
    "./ustreamer/ustreamer",
    f"--device={usb_video}",
    "--format=uyvy",
    "--resolution=1920x1080",
    "--encoder=m2m-image",
    "--drop-same-frames=45",
    "--host=0.0.0.0",
    "--port=9000"
]


ustream_proc = None

KEY_LEFT_CTRL = 0xE0
KEY_LEFT_SHIFT = 0xE1
KEY_LEFT_ALT = 0xE2
KEY_LEFT_GUI = 0xE3  # Windows key
KEY_DELETE = 0x4C
KEY_TAB = 0x2B
KEY_ESC = 0x29
KEY_UP = 0x52
KEY_DOWN = 0x51
KEY_LEFT = 0x50
KEY_RIGHT = 0x4F
KEY_F_KEYS = {f"f{i}": 0x3A + (i - 1) for i in range(1, 13)}
KEYCODES = {
    # Letters
    **{k: v for k, v in zip(range(65, 91), range(0x04, 0x1E))},  # A-Z
    # Numbers
    48: 0x27, 49: 0x1E, 50: 0x1F, 51: 0x20, 52: 0x21,
    53: 0x22, 54: 0x23, 55: 0x24, 56: 0x25, 57: 0x26,
    # Function keys
    112: 0x3A, 113: 0x3B, 114: 0x3C, 115: 0x3D,
    116: 0x3E, 117: 0x3F, 118: 0x40, 119: 0x41,
    120: 0x42, 121: 0x43, 122: 0x44, 123: 0x45,
    # Navigation and editing
    9: 0x2B,   # Tab
    13: 0x28,  # Enter
    27: 0x29,  # Esc
    8: 0x2A,   # Backspace
    46: 0x4C,  # Delete
    35: 0x4D,  # End
    36: 0x4A,  # Home
    33: 0x4B,  # Page Up
    34: 0x4E,  # Page Down
    37: 0x50,  # Left arrow
    38: 0x52,  # Up arrow
    39: 0x4F,  # Right arrow
    40: 0x51,  # Down arrow
    # Symbols and punctuation
    32: 0x2C,  # Space
    45: 0x2D,  # -
    61: 0x2E,  # =
    91: 0x2F,  # [
    93: 0x30,  # ]
    92: 0x31,  # Backslash
    59: 0x33,  # ;
    39: 0x4F,  # '
    96: 0x35,  # `
    44: 0x36,  # ,
    46: 0x37,  # .
    47: 0x38,  # /
    # Modifier keys (used only as modifiers, not sent via KEYCODES)
    16: 0xE1,  # Shift (left)
    17: 0xE0,  # Ctrl (left)
    18: 0xE2,  # Alt (left)
    91: 0xE3,  # Left GUI (Windows key)
    # Right modifiers
    161: 0xE5,  # Right Shift
    162: 0xE4,  # Right Ctrl
    163: 0xE6,  # Right Alt
    92:  0xE7,  # Right GUI
    # Caps Lock
    20: 0x39,
    # Print, Scroll Lock, Pause
    44: 0x46,  # Print Screen (varies)
    145: 0x47, # Scroll Lock
    19: 0x48,  # Pause/Break
    # Numpad (KP)
    96: 0x62, 97: 0x59, 98: 0x5A, 99: 0x5B,
    100: 0x5C, 101: 0x5D, 102: 0x5E, 103: 0x5F,
    104: 0x60, 105: 0x61,
    106: 0x55, 107: 0x57, 109: 0x56,
    110: 0x63, 111: 0x54,
    # Extra keys
    186: 0x33, 187: 0x2E, 188: 0x36, 189: 0x2D,
    190: 0x37, 191: 0x38, 192: 0x35,
    219: 0x2F, 220: 0x31, 221: 0x30, 222: 0x34
}

SHORTCUTS = {
    "ctrl_alt_del":     [KEY_LEFT_CTRL, KEY_LEFT_ALT, KEY_DELETE],
    "ctrl_shift_esc":   [KEY_LEFT_CTRL, KEY_LEFT_SHIFT, KEY_ESC],
    "alt_f4":           [KEY_LEFT_ALT, 0x3D],  # F4
    "win_l":            [KEY_LEFT_GUI, 0x0F],  # L
    "win_d":            [KEY_LEFT_GUI, 0x07],  # D
    "win_tab":          [KEY_LEFT_GUI, KEY_TAB],
    "alt_tab":          [KEY_LEFT_ALT, KEY_TAB],
    "alt_esc":          [KEY_LEFT_ALT, KEY_ESC],
    "win_ctrl_d":       [KEY_LEFT_GUI, KEY_LEFT_CTRL, 0x07],  # D
    "win_ctrl_left":    [KEY_LEFT_GUI, KEY_LEFT_CTRL, KEY_LEFT],
    "win_ctrl_right":   [KEY_LEFT_GUI, KEY_LEFT_CTRL, KEY_RIGHT],
    "win_up":           [KEY_LEFT_GUI, KEY_UP],
    "win_down":         [KEY_LEFT_GUI, KEY_DOWN],
    "win_left":         [KEY_LEFT_GUI, KEY_LEFT],
    "win_right":        [KEY_LEFT_GUI, KEY_RIGHT],
    "ctrl_alt_right":   [KEY_LEFT_CTRL, KEY_LEFT_ALT, KEY_RIGHT],
    "ctrl_alt_left":    [KEY_LEFT_CTRL, KEY_LEFT_ALT, KEY_LEFT],
    **{f"fn_f{i}": [KEY_F_KEYS[f"f{i}"]] for i in range(1, 13)},
    "ctrl_n":           [KEY_LEFT_CTRL, 0x11],  # N
    "ctrl_w":           [KEY_LEFT_CTRL, 0x1A],  # W
    "ctrl_t":           [KEY_LEFT_CTRL, 0x17],  # T
    "ctrl_shift_t":     [KEY_LEFT_CTRL, KEY_LEFT_SHIFT, 0x17],  # T
    "esc":              [0x29],
    "f1":[0x3A], "f2":[0x3B], "f3":[0x3C], "f4":[0x3D], "f5":[0x3E], "f6":[0x3F],
    "f7":[0x40], "f8":[0x41], "f9":[0x42], "f10":[0x43], "f11":[0x44], "f12":[0x45],
}

SHIFTED_KEYS = {
    33, 34, 35, 36, 37, 38, 39, 40, 41,
    126, 33, 64, 35, 36, 37, 94, 38, 42, 40, 41,
    95, 43, 123, 125, 124, 58, 34, 60, 62, 63
}

def send_keycode(keycode, modifier):
    report = bytes([modifier, 0x00, keycode, 0, 0, 0, 0, 0])
    with open(KEYBOARD_PATH, "rb+") as fd:
        fd.write(report)
        fd.write(b'\x00\x00\x00\x00\x00\x00\x00\x00')


def send_keys(hid_codes):
    modifier = 0x00
    keys = []

    for code in hid_codes:
        if 0xE0 <= code <= 0xE7:
            modifier |= (1 << (code - 0xE0))
        else:
            if len(keys) < 6:
                keys.append(code)

    while len(keys) < 6:
        keys.append(0x00)

    report = bytes([modifier, 0x00] + keys)

    with open(KEYBOARD_PATH, "rb+") as fd:
        fd.write(report)  # Press keys
        time.sleep(0.05)
        fd.write(b'\x00\x00\x00\x00\x00\x00\x00\x00')  # Release


def send_mouse(x=0, y=0, buttons=0):
    report = bytes([buttons & 0x07, x & 0xFF, y & 0xFF])
    with open(MOUSE_PATH, "wb") as f:
        f.write(report)

def smooth_mouse_delta(x, y, threshold=1):
    x = x if abs(x) >= threshold else 0
    y = y if abs(y) >= threshold else 0
    return x, y

@app.route("/")
def index():
    return render_template("index.html", stream_host="172.16.38.22")


@app.route("/shortcut/<name>", methods=["POST"])
def shortcut(name):
    if name in SHORTCUTS:
        send_keys(SHORTCUTS[name])
        return f"Sent {name}", 200
    return "Unknown shortcut", 400

@app.route("/keyboard", methods=["POST"])
def keyboard():
    data = request.json
    js_keycodes = data.get("keycodes", [])
    modifier = 0x00
    hid_keycodes = []

    for js_keycode in js_keycodes:
        if js_keycode in [16, 17, 18, 91]:  # Shift, Ctrl, Alt, Meta
            if js_keycode == 16: modifier |= 0x02
            elif js_keycode == 17: modifier |= 0x01
            elif js_keycode == 18: modifier |= 0x04
            elif js_keycode == 91: modifier |= 0x08
        else:
            hid_code = KEYCODES.get(js_keycode, 0)
            if hid_code:
                hid_keycodes.append(hid_code)

    if not hid_keycodes:
        hid_keycodes = [0]  # No key pressed, just modifiers

    try:
        report = bytes([modifier, 0x00] + hid_keycodes[:6] + [0] * (6 - len(hid_keycodes)))
        print(f"[KEYBOARD] modifier={modifier:#04x}, keys={hid_keycodes}")
        with open(KEYBOARD_PATH, "rb+") as fd:
            fd.write(report)
            time.sleep(0.01)
            fd.write(b'\x00\x00\x00\x00\x00\x00\x00\x00')
    except Exception as e:
        print("[!] Keyboard write error:", e)

    return "OK"


@app.route("/mouse", methods=["POST"])
def mouse():
    data = request.json
    x = int(data.get("x", 0))
    y = int(data.get("y", 0))
    buttons = int(data.get("buttons", 0))
    x, y = smooth_mouse_delta(x, y)
    send_mouse(x, y, buttons)
    return "OK"

@app.route("/start_stream")
def start_stream():
    global ustream_proc

    if ustream_proc is not None and ustream_proc.poll() is None:
        return {"status": "already running"}

    try:
        print("[*] Starting uStreamer...")
        ustream_proc = subprocess.Popen(USTREAMER_CMD)
        return {"status": "started"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

if __name__ == "__main__":
    ustream_proc = None

    try:
        print("[*] Starting Flask app on port 5000...")
        app.run(host="0.0.0.0", port=5000)
    finally:
        print("[*] Shutting down uStreamer...")
        if ustream_proc is not None and ustream_proc.poll() is None:
            ustream_proc.send_signal(signal.SIGINT)
            ustream_proc.wait()