from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import subprocess
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or use the specific IP and port if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SERVICE_NAME = "streaming_hid.service"

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
