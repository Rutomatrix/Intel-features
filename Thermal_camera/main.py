#main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import subprocess
import psutil
import logging
import os
import paramiko  # For SSH functionality
app = FastAPI()

# Setup basic logging
logging.basicConfig(level=logging.INFO)

# Allow CORS for all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Utility to check if a script is running
def is_script_running(script_name: str) -> bool:
    for proc in psutil.process_iter(['cmdline']):
        try:
            if proc.info['cmdline'] and any(script_name in cmd for cmd in proc.info['cmdline']):
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False

# Utility to stop a script
def stop_script(script_name: str) -> bool:
    stopped = False
    for proc in psutil.process_iter(['pid', 'cmdline']):
        try:
            if proc.info['cmdline'] and any(script_name in cmd for cmd in proc.info['cmdline']):
                logging.info(f"Stopping {script_name} (PID: {proc.pid})")
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except psutil.TimeoutExpired:
                    proc.kill()
                stopped = True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return stopped
#*****************************************************************
import subprocess

def find_thermal_camera_video_device(vendor_id="0bda", product_id="5830"):
    """Automatically detect the video device ID for a USB thermal camera."""
    video_base = "/dev"
    for i in range(0, 10):  # Check /dev/video0 to /dev/video9
        dev = f"{video_base}/video{i}"
        try:
            result = subprocess.run(["udevadm", "info", "--query=property", "--name", dev],
                                    capture_output=True, text=True)
            if result.returncode == 0:
                output = result.stdout
                if f"ID_VENDOR_ID={vendor_id}" in output and f"ID_MODEL_ID={product_id}" in output:
                    return i  # Found the correct video device number
        except Exception:
            continue
    return None  # If not found

#****************************************************************
# Start camera.py
#@app.post("/start-camera")
@app.get("/start-camera")
async def start_camera():
    if is_script_running("camera.py"):
        return JSONResponse({"status": "info", "message": "camera.py is already running"})
    try:
        subprocess.Popen(["python3", "/home/rpi4/project/camera.py"])
        logging.info("camera.py started")
        return JSONResponse({"status": "success", "message": "camera.py started"})
    except Exception as e:
        logging.error(f"Failed to start camera.py: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

# Stop camera.py
#@app.post("/stop-camera")
@app.get("/stop-camera")
async def stop_camera():
    if stop_script("camera.py"):
        return JSONResponse({"status": "success", "message": "camera.py stopped"})
    return JSONResponse({"status": "info", "message": "camera.py was not running"})
'''#***************************************************************
# Start thermal_camera.py
#@app.post("/start-thermal")
@app.get("/start-thermal")  # Optional GET support
async def start_thermal():
    if is_script_running("thermal_camera.py"):
        return JSONResponse({"status": "info", "message": "thermal_camera.py is already running"})
    try:
        subprocess.Popen(["python3", "/home/rpi/TI/thermal_camera.py", "--device", "0"])
        logging.info("thermal_camera.py started")
        return JSONResponse({"status": "success", "message": "thermal_camera.py started"})
    except Exception as e:
        logging.error(f"Failed to start thermal_camera.py: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

#********************************************
@app.get("/start-thermal")
async def start_thermal(device: int = Query(0, description="Device ID to use")):
    if is_script_running("thermal_camera.py"):
        return JSONResponse({"status": "info", "message": "thermal_camera.py is already running"})
    try:
        subprocess.Popen(["python3", "/home/rpi/TI/thermal_camera.py", "--device", str(device)])
        logging.info(f"Thermal_camera.py started with device {device}")
        return JSONResponse({"status": "success", "message": f"thermal_camera.py started with device {device}"})
    except Exception as e:
        logging.error(f"Failed to start thermal_camera.py: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)
'''
#*******************************************
@app.get("/start-thermal")
async def start_thermal():
    if is_script_running("thermal_camera.py"):
        return JSONResponse({"status": "info", "message": "thermal_camera.py is already running"})

    device = find_thermal_camera_video_device()
    if device is None:
        return JSONResponse({"status": "error", "message": "Thermal USB camera not found"}, status_code=404)

    try:
        subprocess.Popen(["python3", "/home/rpi4/project/thermal_camera.py", "--device", str(device)])
        logging.info(f"thermal_camera.py started with USB thermal camera at /dev/video{device}")
        return JSONResponse({"status": "success", "message": f"thermal_camera.py started with device {device}"})
    except Exception as e:
        logging.error(f"Failed to start thermal_camera.py: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

#********************************************
# Stop thermal_camera.py
#@app.post("/stop-thermal")
@app.get("/stop-thermal")
async def stop_thermal():
    if stop_script("thermal_camera.py"):
        return JSONResponse({"status": "success", "message": "thermal_camera.py stopped"})
    return JSONResponse({"status": "info", "message": "thermal_camera.py was not running"})
#************************************************************************
# Check running status of both scripts
@app.get("/status")
async def get_status():
    return {
        "camera.py": "running" if is_script_running("camera.py") else "stopped",
        "thermal_camera.py": "running" if is_script_running("thermal_camera.py") else "stopped"
    }
'''#**************************************************
@app.get("/start-servo")
async def start_servo():
    response = {}

    if is_script_running("servo.py"):
        response["servo.py"] = "already running"
    else:
        try:
            subprocess.Popen(["python3", "/home/rpi4/project/servo.py"])
            logging.info("servo.py started")
            response["servo.py"] = "started"
        except Exception as e:
            logging.error(f"Failed to start servo.py: {e}")
            response["servo.py"] = f"error: {e}"

    return JSONResponse({"status": "success", "message": response})
'''
@app.get("/start-servo")
async def start_servo():
    response = {}

    # Ensure pigpiod service is started and enabled
    try:
        subprocess.run(["sudo", "systemctl", "start", "pigpiod"], check=True)
        subprocess.run(["sudo", "systemctl", "enable", "pigpiod"], check=True)
        logging.info("pigpiod service started and enabled")
        response["pigpiod"] = "started and enabled"
    except Exception as e:
        logging.error(f"Failed to start/enable pigpiod: {e}")
        response["pigpiod"] = f"error: {e}"
        return JSONResponse({"status": "failed", "message": response})

    # Start servo.py only if not already running
    if is_script_running("servo.py"):
        response["servo.py"] = "already running"
    else:
        try:
            subprocess.Popen(["python3", "/home/rpi4/project/servo.py"])
            logging.info("servo.py started")
            response["servo.py"] = "started"
        except Exception as e:
            logging.error(f"Failed to start servo.py: {e}")
            response["servo.py"] = f"error: {e}"

    return JSONResponse({"status": "success", "message": response})

#stop servo
@app.get("/stop-servo")
async def stop_all_servos():
    result = {}

    if stop_script("servo.py"):
        result["servo.py"] = "stopped"
    else:
        result["servo.py"] = "was not running"


    return JSONResponse({"status": "success", "message": result})

#*************************************************

# Run with: python3 main.py
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="100.124.235.42", port=8000)
'''
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="100.68.107.103",   # Your server IP
        port=8000,               # HTTPS port
        ssl_keyfile="server.key",         # Path to your private key
        ssl_certfile="server.crt"         # Path to your certificate
    )
'''