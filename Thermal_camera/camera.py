#camera.py
import io
import time
import threading
from fastapi import FastAPI
from fastapi.responses import StreamingResponse, HTMLResponse, JSONResponse
from picamera2 import Picamera2
import uvicorn
import paramiko  # For SSH functionality
from fastapi.middleware.cors import CORSMiddleware
import cv2
import numpy as np
app = FastAPI()
 
# Enable CORS (allow all origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
 
# Initialize Camera
picam2 = Picamera2()
picam2.configure(picam2.create_video_configuration(main={"size": (1920,1580)}))
picam2.set_controls({"AfMode": 2})
picam2.start()
 
"""while True:
    metadata = picam2.capture_metadata()
    lens_position = metadata.get("LensPosition", "N/A")
    focus_status = metadata.get("FocusStatus", "N/A")
    print(f"Lens Position: {lens_position}, Focus Status: {focus_status}")
    time.sleep(0.5)"""
 
 
latest_frame = None
frame_lock = threading.Lock()
 
# Function to Capture Frames Continuously
def capture_frames():
    global latest_frame
    while True:
        output = io.BytesIO()
        picam2.capture_file(output, format="jpeg")
        with frame_lock:
            latest_frame = output.getvalue()
        time.sleep(0.1)  # 10 FPS
'''#****************************************
def capture_frames():
    global latest_frame
    while True:
        output = io.BytesIO()
        picam2.capture_file(output, format="jpeg")
        output.seek(0)
        # Convert image bytes to NumPy array
        image_array = np.frombuffer(output.read(), dtype=np.uint8)
        frame = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
 
        # Rotate the frame 90 degrees clockwise
        frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
 
        # Encode back to JPEG
        success, encoded_image = cv2.imencode('.jpg', frame)
        if success:
            with frame_lock:
                latest_frame = encoded_image.tobytes()
 
        time.sleep(0.1)  # 10 FPS
 
 
#****************************************'''
# Start Frame Capture Thread
threading.Thread(target=capture_frames, daemon=True).start()
 
# HTML Page for Video Streaming
HTML_PAGE = """\
<html>
<head>
<title>FastAPI - PiCamera2 Streaming</title>
</head>
<body>
<h1>FastAPI - Picamera2 MJPEG Streaming</h1>
<img src="/stream.mjpg" width="1920" height="1580" />
</body>
</html>
"""
 
# MJPEG Streaming Generator
def mjpeg_stream():
    while True:
        with frame_lock:
            frame = latest_frame if latest_frame else b""
        if frame:
            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n"
                   b"Content-Length: " + str(len(frame)).encode() + b"\r\n"
                   b"\r\n" + frame + b"\r\n")
        time.sleep(0.1)
 
# Routes
@app.get("/", response_class=HTMLResponse)
async def homepage():
    return HTML_PAGE
 
@app.get("/camera.mjpg")
async def video_feed():
    return StreamingResponse(mjpeg_stream(), media_type="multipart/x-mixed-replace; boundary=frame")
 
@app.get("/camera_verified")
async def get_verified():
    """Return a JSON response with 'verified'."""
    try:
        # Initialize SSH client
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
 
        # Connect to the remote server (update credentials as necessary)
        client.connect("100.124.235.42", username="rpi4", password="pi123")
 
        # Optionally verify connection
        # stdin, stdout, stderr = client.exec_command('echo "connected"')
 
        client.close()
        return JSONResponse({"ok": True, "status": "verified"})
 
    except Exception as e:
        return JSONResponse({"ok": False, "status": f"Error: {str(e)}"}, status_code=500)
 
# Uvicorn Run
'''if __name__ == "__main__":
    uvicorn.run(app, host="100.68.107.103", port=8001, ssl_keyfile="server.key", ssl_certfile="server.crt")
'''
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="100.124.235.42", port=8001)