from fastapi import FastAPI, Request # ADDED 'Request' previously
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates # <-- ADD THIS LINE
from fastapi.responses import HTMLResponse # <-- ADD THIS LINE
import subprocess
import uvicorn
import socket # ADDED previously

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or use the specific IP and port if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SERVICE_NAME = "streaming_hid.service"
templates = Jinja2Templates(directory="templates")
# --- ADDED: IP Detection Function ---
def get_local_ip():
    """Dynamically finds the local IP address of the machine."""
    s = None
    try:
        # Use a temporary socket to determine the local IP used for external connections.
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip_address = s.getsockname()[0]
        return ip_address
    except Exception:
        # Fallback if network is unavailable
        return "127.0.0.1"
    finally:
        if s:
            s.close()
# ------------------------------------


# --- ADDED: Endpoint to serve the HTML Launcher ---
@app.get("/", response_class=HTMLResponse)
async def launcher_page(request: Request):
    rpi_ip = get_local_ip()
    
    # Render the HTML file (named 'launcher.html' in the templates folder)
    # and inject the dynamic IP and port numbers.
    return templates.TemplateResponse(
        "launcher.html",
        {
            "request": request,
            "stream_host": rpi_ip,
            "fastapi_port": 8000, # FastAPI is running on 8000
            "flask_port": 5000    # KVM app is expected on 5000
        }
    )
# ----------------------------------------------------
@app.post("/start_stream")
def start_stream():
    try:
        subprocess.run(["sudo", "systemctl", "start", SERVICE_NAME], check=True)
        return {"status": "started"}
    except subprocess.CalledProcessError as e:
        return {"status": "error", "detail": str(e)}

@app.post("/stop_stream")
def stop_stream():
    try:
        subprocess.run(["sudo", "systemctl", "stop", SERVICE_NAME], check=True)
        return {"status": "stopped"}
    except subprocess.CalledProcessError as e:
        return {"status": "error", "detail": str(e)}

@app.get("/status")
def status():
    result = subprocess.run(["systemctl", "is-active", SERVICE_NAME], capture_output=True, text=True)
    return {"status": result.stdout.strip()}


# ðŸ”¸ This is what actually runs the server and keeps the process alive
if __name__ == "__main__":
    uvicorn.run("start_streaming:app", host="0.0.0.0", port=8000, reload=False)
