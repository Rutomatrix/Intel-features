from flask import Flask, jsonify, render_template, request
import subprocess
import os
import re

app = Flask(__name__)

# Base SPI parameters
SPI_BASE = ["sudo", "flashrom", "-p", "linux_spi:dev=/dev/spidev0.0,spispeed=15000"]
# Chip specification
CHIP = ["-c", "MT25QL01G"]

def run_cmd(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    return {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}

@app.route('/')
def index():
    return render_template('index1.html')

@app.route('/detect', methods=['POST'])
def detect():
    cmd = SPI_BASE
    raw = run_cmd(cmd)
    
    # Extract only lines with 'Found' and 'flash chip'
    lines = raw['stdout'].splitlines()
    found_chips = [line for line in lines if 'Found' in line and 'flash chip' in line]
    
    return jsonify({
        "detected_chips": found_chips,
        "chip_count": len(found_chips),
        "returncode": raw["returncode"]
    })

@app.route('/read', methods=['POST'])
def read_chip():
    base_dir = "/home/rpi/Documents"
    base_name = "backup"
    extension = ".bin"
    
    os.makedirs(base_dir, exist_ok=True)

    # Find next available backup file number
    existing_files = os.listdir(base_dir)
    pattern = re.compile(rf"{base_name}(\d+){re.escape(extension)}")

    numbers = [
        int(match.group(1)) for filename in existing_files
        if (match := pattern.match(filename))
    ]

    next_num = max(numbers) + 1 if numbers else 2  # Start from backup2.bin
    filename = f"{base_name}{next_num}{extension}"
    full_path = os.path.join(base_dir, filename)

    # Run SPI read
    cmd = SPI_BASE + CHIP + ["-r", full_path]
    result = run_cmd(cmd)

    if os.path.exists(full_path):
        return jsonify({
            "status": f"Reading complete: {filename}",
            "file_created": True,
            "file_name": filename,
            "file_size": os.path.getsize(full_path)
        })
    else:
        return jsonify({
            "status": f"Reading failed for {filename}",
            "file_created": False
        })

@app.route('/list-files', methods=['POST'])
def list_files():
    directory = "/home/rpi/Documents"
    try:
        files = [os.path.join(directory, f)
                 for f in os.listdir(directory)
                 if f.endswith(".bin") and os.path.isfile(os.path.join(directory, f))]
        return jsonify({"files": files})
    except Exception as e:
        return jsonify({"error": str(e), "files": []}), 500

@app.route('/write', methods=['POST'])
def write_chip():
    data = request.get_json() or {}
    firmware_path = data.get("firmware_path")
    
    if not firmware_path:
        return jsonify({
            "error": "firmware_path is required",
            "returncode": -1,
            "file_verified": False
        }), 400

    if not os.path.exists(firmware_path):
        return jsonify({
            "error": "File not found",
            "returncode": -1,
            "file_verified": False
        }), 404

    # Build and execute command
    cmd = SPI_BASE + CHIP + ["-w", firmware_path]
    # result = run_cmd(cmd)  # Uncomment for real write
    result = {"returncode": 0, "stdout": "WRITE COMMAND SKIPPED (disabled for safety)", "stderr": ""}
    result['file_verified'] = result['returncode'] == 0
    
    return jsonify(result)

if __name__ == '__main__':
    app.run(host='100.109.50.57', port=5003, debug=True)
