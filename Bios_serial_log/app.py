from flask import Flask, jsonify, render_template, request, session
import subprocess
import os
import threading
import time
from datetime import datetime
from queue import Queue, Empty
import secrets

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)  # Generate a secret key for sessions

# Configuration
LOG_FILES_DIR = '/home/rpi/serial_logs'  # Update this path to your log files directory
current_process = None
process_lock = threading.Lock()
log_queue = Queue()
reader_thread = None
active_session_id = None  # Track which session owns the process
last_heartbeat = {}  # Track last heartbeat from each session
HEARTBEAT_TIMEOUT = 10  # seconds

def read_output(process, queue):
    """Read subprocess output in a separate thread"""
    try:
        for line in iter(process.stdout.readline, ''):
            if line:
                queue.put(line.strip())
            if process.poll() is not None:
                break
    except Exception as e:
        print(f"Error reading output: {e}")
    finally:
        process.stdout.close()

@app.route('/')
def index():
    # Generate a unique session ID for this tab/client
    if 'session_id' not in session:
        session['session_id'] = secrets.token_hex(8)
    return render_template('index.html')

@app.route('/start-logging', methods=['GET', 'POST'])
def start_logging():
    global current_process, reader_thread, log_queue, active_session_id
    
    current_session = session.get('session_id')
    
    with process_lock:
        # Check if another session owns the process
        if current_process is not None and active_session_id != current_session:
            return jsonify({
                'status': 'error', 
                'message': 'Logging is already active in another tab. Please stop it there first or close that tab.'
            }), 409
        
        # If the same session is restarting, stop the existing process
        if current_process is not None and active_session_id == current_session:
            try:
                current_process.terminate()
                current_process.wait(timeout=5)
            except Exception:
                try:
                    current_process.kill()
                except:
                    pass
            finally:
                current_process = None
                reader_thread = None
        
        try:
            # Clear the queue
            while not log_queue.empty():
                try:
                    log_queue.get_nowait()
                except Empty:
                    break
            
            # Start the script in background mode
            current_process = subprocess.Popen(
                ['sudo', '/home/rpi/Bios_serial_log.sh'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Assign ownership to this session
            active_session_id = current_session
            
            # Start reader thread
            reader_thread = threading.Thread(target=read_output, args=(current_process, log_queue), daemon=True)
            reader_thread.start()
            
            return jsonify({'status': 'started', 'message': 'Logging started successfully'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/stop-logging', methods=['GET', 'POST'])
def stop_logging():
    global current_process, reader_thread, active_session_id
    
    current_session = session.get('session_id')
    
    with process_lock:
        if current_process is None:
            return jsonify({'status': 'not_running', 'message': 'No logging process running'})
        
        # Check if this session owns the process
        if active_session_id != current_session:
            return jsonify({
                'status': 'error',
                'message': 'You cannot stop logging started by another tab'
            }), 403
        
        try:
            current_process.terminate()
            current_process.wait(timeout=5)
        except Exception as e:
            try:
                current_process.kill()
            except:
                pass
        finally:
            current_process = None
            reader_thread = None
            active_session_id = None
            
        return jsonify({'status': 'stopped', 'message': 'Logging stopped successfully'})

@app.route('/get-logs', methods=['GET'])
def get_logs():
    global log_queue, active_session_id
    logs = []
    
    current_session = session.get('session_id')
    
    # Allow any session to read logs, but indicate if they own the process
    is_owner = (active_session_id == current_session)
    
    try:
        # Get all available logs from queue (non-blocking)
        while not log_queue.empty() and len(logs) < 100:
            try:
                line = log_queue.get_nowait()
                if line:
                    logs.append(line)
            except Empty:
                break
    except Exception as e:
        print(f"Error reading logs from queue: {e}")
    
    return jsonify({
        'logs': logs,
        'is_owner': is_owner,
        'has_active_process': (current_process is not None)
    })

@app.route('/list-files', methods=['GET'])
def list_files():
    try:
        if not os.path.exists(LOG_FILES_DIR):
            return jsonify({'files': [], 'error': 'Log directory not found'})
        
        files = []
        for filename in os.listdir(LOG_FILES_DIR):
            filepath = os.path.join(LOG_FILES_DIR, filename)
            if os.path.isfile(filepath) and filename.endswith('.txt'):
                stat = os.stat(filepath)
                files.append({
                    'name': filename,
                    'size': stat.st_size,
                    'modified': stat.st_mtime
                })
        
        # Sort by modified time (newest first)
        files.sort(key=lambda x: x['modified'], reverse=True)
        return jsonify({'files': files})
    except Exception as e:
        return jsonify({'files': [], 'error': str(e)}), 500

@app.route('/get-file/<filename>', methods=['GET'])
def get_file(filename):
    try:
        filepath = os.path.join(LOG_FILES_DIR, filename)
        
        # Security check - ensure file is within LOG_FILES_DIR
        if not os.path.abspath(filepath).startswith(os.path.abspath(LOG_FILES_DIR)):
            return jsonify({'error': 'Invalid file path'}), 403
        
        if not os.path.exists(filepath):
            return jsonify({'error': 'File not found'}), 404
        
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        return jsonify({'content': content})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='100.109.50.57', port=1848, debug=True)
