import serial
import time
import re
from flask import Flask, jsonify, render_template
from threading import Thread, Lock, Event
from flask_cors import CORS
# Configuration
PORT = '/dev/serial0'
BAUDRATE = 115200
READ_AFTER_FIRST_CODE = 60  # seconds
LAST_EXPECTED_POSTCODE = "e3"

app = Flask(__name__)
CORS(app)
# Shared variables
postcodes = []
lock = Lock()
stop_event = Event()
reading_done = Event()
reading_thread = None


def serial_reader():
    global postcodes
    timer_started = False
    start_time = None
    e3_count = 0  # Track number of 'e3' occurrences

    try:
        with serial.Serial(
            port=PORT,
            baudrate=BAUDRATE,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            xonxoff=False,
            rtscts=False,
            dsrdtr=False,
            timeout=1
        ) as ser:
            print(f"[INFO] Waiting for first postcode on {PORT} at {BAUDRATE} baud...\n")
            ser.flushInput()
            while not stop_event.is_set():
                raw_bytes = ser.readline()
                if raw_bytes:
                    decoded = raw_bytes.decode('ascii', errors='ignore').strip()
                    matches = re.findall(r'\b[0-9a-fA-F]{2}\b', decoded)

                    with lock:
                        for code in matches:
                            print(f"[RECEIVED] Postcode: {code}")
                            postcodes.append(code)

                            if code.lower() == LAST_EXPECTED_POSTCODE:
                                e3_count += 1
                                print(f"[INFO] 'e3' received ({e3_count}/2)")

                                if e3_count == 3:
                                    print("[INFO] Second 'e3' received. Stopping reader.")
                                    reading_done.set()
                                    stop_event.set()
                                    break

                            if not timer_started:
                                timer_started = True
                                start_time = time.time()

                if timer_started and (time.time() - start_time > READ_AFTER_FIRST_CODE):
                    print("[TIMEOUT] 60 seconds passed.")
                    reading_done.set()
                    stop_event.set()

                time.sleep(0.01)

    except serial.SerialException as e:
        print(f"[ERROR] Serial error: {e}")
    except KeyboardInterrupt:
        print("[INFO] Interrupted by user.")


@app.route('/')
def index():
    return render_template('index.html')
@app.route('/get_data')
def get_data():
    global reading_thread, postcodes

    # Stop any previous reading thread if it's still alive
    if reading_thread is not None and reading_thread.is_alive():
        print("[INFO] Waiting for previous thread to stop...")
        stop_event.set()
        reading_thread.join(timeout=2)  # Wait max 2 seconds
        print("[INFO] Previous reading thread stopped.")

    # Reset shared state
    with lock:
        postcodes.clear()
    stop_event.clear()
    reading_done.clear()

    # Start a new reading thread
    reading_thread = Thread(target=serial_reader)
    reading_thread.start()

    return jsonify({"status": "started", "postcodes": []})



@app.route('/poll_data')
def poll_data():
    with lock:
        data_copy = postcodes.copy()

    if reading_done.is_set():
        return jsonify({"status": "success", "postcodes": data_copy})
    else:
        return jsonify({"status": "running", "postcodes": data_copy})


if __name__ == "__main__":
    app.run(host="10.66.179.71", port=5010, debug=True)