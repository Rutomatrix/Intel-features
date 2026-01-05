import os
import glob
import subprocess
import threading
import time
import re
from flask import Flask, jsonify, render_template, send_file, request
from flask_cors import CORS
from datetime import datetime

# Configuration
LOGDIR = "/home/rpi/postcode_logs"
PORT = "/dev/ttyAMA0"
BAUDRATE = 115200

app = Flask(__name__)
CORS(app)

# Ensure log directory exists
os.makedirs(LOGDIR, exist_ok=True)

# Shared variables
postcodes = []
lock = threading.Lock()
stop_event = threading.Event()
reading_done = threading.Event()
reading_thread = None
minicom_process = None
current_logfile = None

def clean_ansi_escape_codes(text):
    """Remove ANSI escape codes from text"""
    # Regex to remove ANSI escape sequences
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

def parse_postcode_from_line(line):
    """Extract postcode from a cleaned line of text"""
    # Clean the line first
    clean_line = clean_ansi_escape_codes(line)
    
    # Try multiple patterns to extract postcodes
    patterns = [
        r'\b([0-9a-fA-F]{2})\b',  # Standard hex codes
        r'([0-9a-fA-F]{2})',       # Any 2-character hex
        r'0x([0-9a-fA-F]{2})',     # 0x prefixed
        r'([0-9a-fA-F]{2})h',      # h suffixed
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, clean_line)
        if matches:
            return matches[0].lower()  # Return first match in lowercase
    return None

def run_minicom():
    """Run minicom and capture output in real-time"""
    global postcodes, minicom_process, current_logfile
    
    print("[INFO] Starting minicom...")
    
    # Create a unique log file name
    timestamp = datetime.now().strftime("%d-%m-%y-%H-%M-%S")
    current_logfile = os.path.join(LOGDIR, f"POSTCODE_LOG_{timestamp}.txt")
    
    try:
        # Start minicom directly (not through bash script)
        cmd = f"sudo minicom -b {BAUDRATE} -o -D {PORT}"
        
        minicom_process = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            universal_newlines=True,
            preexec_fn=os.setsid
        )
        
        print(f"[INFO] Minicom started with PID: {minicom_process.pid}")
        print(f"[INFO] Log file: {current_logfile}")
        
        # Open log file for writing
        with open(current_logfile, 'w') as log_file:
            log_file.write(f"Postcode Log - Started at {timestamp}\n")
            log_file.write(f"Port: {PORT}, Baudrate: {BAUDRATE}\n")
            log_file.write("="*50 + "\n")
            
            start_time = time.time()
            e3_count = 0
            last_activity = time.time()
            
            # Read output line by line
            for line in iter(minicom_process.stdout.readline, ''):
                if stop_event.is_set():
                    break
                
                line = line.strip()
                if line:
                    # Clean ANSI escape codes
                    clean_line = clean_ansi_escape_codes(line)
                    
                    # Write to log file
                    timestamp_str = datetime.now().strftime("%H:%M:%S")
                    log_entry = f"[{timestamp_str}] {clean_line}\n"
                    log_file.write(log_entry)
                    log_file.flush()
                    
                    print(f"[MINICOM] {clean_line}")
                    
                    # Parse postcode from the cleaned line
                    postcode = parse_postcode_from_line(clean_line)
                    
                    if postcode:
                        with lock:
                            postcodes.append({
                                "code": postcode,
                                "timestamp": timestamp_str,
                                "raw": clean_line
                            })
                            
                            # Check for termination condition
                            if postcode == "e3":
                                e3_count += 1
                                print(f"[INFO] 'e3' received ({e3_count}/2)")
                                if e3_count == 2:
                                    print("[INFO] Second 'e3' received. Stopping.")
                                    reading_done.set()
                                    stop_event.set()
                                    break
                    
                    # Update last activity time
                    last_activity = time.time()
                
                # Check for timeout (60 seconds of inactivity)
                if time.time() - last_activity > 60 and last_activity > start_time:
                    print("[TIMEOUT] 60 seconds of inactivity. Stopping.")
                    reading_done.set()
                    stop_event.set()
                    break
            
            # Write summary
            with lock:
                total_codes = len(postcodes)
                log_file.write(f"\nSession ended at {datetime.now().strftime('%H:%M:%S')}\n")
                log_file.write(f"Total postcodes captured: {total_codes}\n")
                print(f"[INFO] Session ended. Total postcodes: {total_codes}")
    
    except Exception as e:
        print(f"[ERROR] Error in minicom execution: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Ensure process is terminated
        if minicom_process and minicom_process.poll() is None:
            print("[INFO] Terminating minicom process...")
            try:
                os.killpg(os.getpgid(minicom_process.pid), 15)  # SIGTERM
                minicom_process.wait(timeout=5)
            except:
                pass
        
        reading_done.set()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start')
def start_reading():
    """Start minicom reading"""
    global reading_thread, postcodes, minicom_process
    
    print("[API] /start - Starting minicom reading...")
    
    # Stop any existing process
    if minicom_process and minicom_process.poll() is None:
        print("[INFO] Stopping existing minicom process...")
        try:
            os.killpg(os.getpgid(minicom_process.pid), 15)
            minicom_process.wait(timeout=2)
        except:
            pass
    
    if reading_thread and reading_thread.is_alive():
        print("[INFO] Waiting for previous thread to finish...")
        stop_event.set()
        reading_thread.join(timeout=2)
    
    # Reset state
    with lock:
        postcodes.clear()
    
    stop_event.clear()
    reading_done.clear()
    
    # Start new thread
    reading_thread = threading.Thread(target=run_minicom)
    reading_thread.daemon = True
    reading_thread.start()
    
    # Give it a moment to start
    time.sleep(1)
    
    return jsonify({
        "status": "started", 
        "message": "Minicom reading started"
    })

@app.route('/stop')
def stop_reading():
    """Stop minicom reading"""
    global minicom_process
    
    print("[API] /stop - Stopping minicom...")
    
    stop_event.set()
    
    if minicom_process and minicom_process.poll() is None:
        try:
            os.killpg(os.getpgid(minicom_process.pid), 15)
            minicom_process.wait(timeout=2)
            print("[INFO] Minicom process stopped")
        except:
            pass
    
    return jsonify({"status": "success", "message": "Reading stopped"})

@app.route('/poll')
def poll_data():
    """Poll for live data updates"""
    with lock:
        data_copy = postcodes.copy()
    
    if reading_done.is_set():
        return jsonify({
            "status": "completed", 
            "postcodes": data_copy,
            "count": len(data_copy),
            "message": "Reading completed"
        })
    else:
        return jsonify({
            "status": "running", 
            "postcodes": data_copy,
            "count": len(data_copy),
            "message": "Reading in progress"
        })

@app.route('/clear')
def clear_data():
    """Clear live data buffer"""
    global postcodes
    with lock:
        postcodes.clear()
    return jsonify({"status": "success", "message": "Live data cleared"})

@app.route('/list_logs')
def list_logs():
    """List all log files in the directory"""
    try:
        log_files = []
        
        # Get all .txt files
        for file_path in glob.glob(os.path.join(LOGDIR, "*.txt")):
            file_stat = os.stat(file_path)
            log_files.append({
                "name": os.path.basename(file_path),
                "path": file_path,
                "size": file_stat.st_size,
                "modified": datetime.fromtimestamp(file_stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                "created": datetime.fromtimestamp(file_stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
            })
        
        # Sort by modified time (newest first)
        log_files.sort(key=lambda x: x["modified"], reverse=True)
        
        return jsonify({"status": "success", "logs": log_files})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/get_log/<filename>')
def get_log(filename):
    """Get log file content"""
    try:
        file_path = os.path.join(LOGDIR, filename)
        
        if not os.path.exists(file_path):
            return jsonify({"status": "error", "message": "File not found"}), 404
        
        # Check if download is requested
        download = request.args.get('download', 'false').lower() == 'true'
        
        if download:
            return send_file(
                file_path,
                as_attachment=True,
                download_name=filename,
                mimetype='text/plain'
            )
        else:
            # Read and return content
            with open(file_path, 'r') as f:
                content = f.read()
            
            return jsonify({
                "status": "success",
                "filename": filename,
                "content": content,
                "lines": len(content.split('\n')),
                "size": os.path.getsize(file_path)
            })
    
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/delete_log/<filename>')
def delete_log(filename):
    """Delete a log file"""
    try:
        file_path = os.path.join(LOGDIR, filename)
        
        if not os.path.exists(file_path):
            return jsonify({"status": "error", "message": "File not found"}), 404
        
        os.remove(file_path)
        return jsonify({"status": "success", "message": f"Deleted {filename}"})
    
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/status')
def status():
    """Check server status"""
    return jsonify({
        "status": "running",
        "port": PORT,
        "baudrate": BAUDRATE,
        "log_dir": LOGDIR,
        "log_dir_exists": os.path.exists(LOGDIR),
        "postcodes_in_memory": len(postcodes),
        "minicom_running": minicom_process is not None and minicom_process.poll() is None
    })

if __name__ == "__main__":
    print("="*60)
    print("Postcode Logger Server")
    print(f"Port: {PORT}")
    print(f"Baudrate: {BAUDRATE}")
    print(f"Log Directory: {LOGDIR}")
    print("="*60)
    print("\nAvailable endpoints:")
    print("  /              - Web interface")
    print("  /start         - Start reading")
    print("  /stop          - Stop reading")
    print("  /poll          - Get current postcodes")
    print("  /clear         - Clear memory")
    print("  /list_logs     - List saved log files")
    print("  /status        - Server status")
    print("="*60)
    print("\nStarting Flask server on 0.0.0.0:5010")
    print("Open browser to: http://<raspberry-pi-ip>:5010")
    
    app.run(host="0.0.0.0", port=5015, debug=True, use_reloader=False)
