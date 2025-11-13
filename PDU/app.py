from flask import Flask, render_template, request, jsonify
import RPi.GPIO as GPIO
import atexit
import time

# Configuration
RELAY_GPIO = 21  # BCM numbering (GPIO21 -> physical pin 40)
RELAY_ACTIVE_LOW = False  # You said: active LOW

# Initialize GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(RELAY_GPIO, GPIO.OUT)

# If active-low then keep relay off by setting HIGH, else set LOW
def set_relay_off_initial():
    if RELAY_ACTIVE_LOW:
        GPIO.output(RELAY_GPIO, GPIO.HIGH)
    else:
        GPIO.output(RELAY_GPIO, GPIO.LOW)

set_relay_off_initial()

# Cleanup on exit
def cleanup():
    try:
        # Leave relay OFF on shutdown
        set_relay_off_initial()
        GPIO.cleanup()
    except Exception:
        pass

atexit.register(cleanup)

app = Flask(__name__, static_folder="static", template_folder="templates")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/status", methods=["GET"])
def status():
    # Read current pin: note that reading the pin returns the current output level.
    pin_level = GPIO.input(RELAY_GPIO)
    # Interpret according to active-low
    relay_on = (pin_level == GPIO.LOW) if RELAY_ACTIVE_LOW else (pin_level == GPIO.HIGH)
    return jsonify({"relay_on": bool(relay_on)})

@app.route("/api/toggle", methods=["POST"])
def toggle():
    data = request.get_json() or {}
    action = (data.get("action") or "").lower()
    if action not in ("on", "off"):
        return jsonify({"error": "invalid action"}), 400

    try:
        if action == "on":
            # For active LOW set GPIO LOW to turn ON
            if RELAY_ACTIVE_LOW:
                GPIO.output(RELAY_GPIO, GPIO.LOW)
            else:
                GPIO.output(RELAY_GPIO, GPIO.HIGH)
        else:  # off
            if RELAY_ACTIVE_LOW:
                GPIO.output(RELAY_GPIO, GPIO.HIGH)
            else:
                GPIO.output(RELAY_GPIO, GPIO.LOW)

        # small debounce / safety delay for hardware response
        time.sleep(0.05)

        # return new status
        pin_level = GPIO.input(RELAY_GPIO)
        relay_on = (pin_level == GPIO.LOW) if RELAY_ACTIVE_LOW else (pin_level == GPIO.HIGH)
        return jsonify({"relay_on": bool(relay_on)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    # Bind to 0.0.0.0 so available on Tailscale IP
    app.run(host="0.0.0.0", port=5000, debug=False)
