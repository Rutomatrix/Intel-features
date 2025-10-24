#!/usr/bin/env python3
from flask import Flask, render_template, jsonify
import subprocess
import os
from pathlib import Path
from flask_cors import CORS

app = Flask(__name__, template_folder='templates')
CORS(app)

# Base directory where all scripts are located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SCRIPTS = {
    'status': os.path.join(BASE_DIR, 'web_status_reader_fixed.sh'),
    'power_on': os.path.join(BASE_DIR, 'Atx_Power_On.sh'),
    'power_off': os.path.join(BASE_DIR, 'Atx_Power_Off.sh'),
    'power_reset': os.path.join(BASE_DIR, 'Atx_Power_Reset.sh')
}

def run_script(script_path):
    """Run a shell script and capture its output."""
    try:
        result = subprocess.run(
            ['/bin/bash', script_path],
            capture_output=True,
            text=True,
            timeout=10
        )
        output = result.stdout.strip() or result.stderr.strip()
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except Exception as e:
        return False, str(e)

@app.route('/')
def index():
    """Render the web UI."""
    return render_template('index.html')

@app.route('/state')
def get_state():
    """Return the current server state."""
    success, output = run_script(SCRIPTS['status'])
    if success:
        output = output.lower().strip()
        status_map = {
            'server off': {'state': 'SERVER OFF', 'status': 'off'},
            'shutdown': {'state': 'SHUTDOWN', 'status': 'off'},
            'hybernate': {'state': 'HYBERNATED', 'status': 'off'},
            'active': {'state': 'ACTIVE', 'status': 'active'}
        }
        status_info = status_map.get(output, {'state': f"Status: {output}", 'status': 'unknown'})
        return jsonify(status_info)
    return jsonify({'state': f"Error: {output}", 'status': 'error'})

@app.route('/power/on')
def power_on():
    success, output = run_script(SCRIPTS['power_on'])
    status = 'success' if success else 'error'
    return jsonify({'status': status, 'message': output})

@app.route('/power/off')
def power_off():
    success, output = run_script(SCRIPTS['power_off'])
    status = 'success' if success else 'error'
    return jsonify({'status': status, 'message': output})

@app.route('/power/reset')
def power_reset():
    success, output = run_script(SCRIPTS['power_reset'])
    status = 'success' if success else 'error'
    return jsonify({'status': status, 'message': output})

if __name__ == '__main__':
    # Check scripts exist
    for name, path in SCRIPTS.items():
        if not os.path.exists(path):
            print(f"Error: Missing {name} script at {path}")
        elif not os.access(path, os.X_OK):
            print(f"Error: Script not executable: {path}")

    app.run(host='0.0.0.0', port=8003, debug=True)
