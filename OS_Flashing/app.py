from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import FileResponse
import subprocess
from fastapi.middleware.cors import CORSMiddleware
import os
import time

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change based on your frontend port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ISO_DIR = "/home/rpi/os"
LUN_FILE = "/sys/kernel/config/usb_gadget/composite_gadget/functions/mass_storage.usb0/lun.0/file"

@app.get("/list")
def list_isos():
    """List available ISO files in os folder"""
    files = [f for f in os.listdir(ISO_DIR) if f.endswith(".iso")]
    return {"available_isos": files}

@app.post("/mount")
def mount_iso(filename: str = Query(..., description="ISO filename")):
    iso_path = os.path.join(ISO_DIR, filename)
    lun_file = "/sys/kernel/config/usb_gadget/composite_gadget/functions/mass_storage.usb0/lun.0/file"
    udc_file = "/sys/kernel/config/usb_gadget/composite_gadget/UDC"

    if not os.path.exists(iso_path):
        raise HTTPException(status_code=404, detail="ISO file not found")

    if not os.path.exists(lun_file):
        raise HTTPException(status_code=500, detail="Mass storage function not available")

    try:
        # Equivalent manual command:
        # echo "/home/rpi/os/ubuntu.iso" | sudo tee /sys/kernel/config/usb_gadget/.../lun.0/file
        subprocess.run(
            f'echo "{iso_path}" | sudo tee {lun_file}',
            shell=True,
            check=True
        )

        # Equivalent manual:
        # echo "" | sudo tee /sys/kernel/config/usb_gadget/.../UDC
        # sleep 1
        # echo "fe980000.usb" | sudo tee /sys/kernel/config/usb_gadget/.../UDC
        if os.path.exists(udc_file):
            with open(udc_file, "r") as f:
                udc = f.read().strip()

            subprocess.run(f'echo "" | sudo tee {udc_file}', shell=True, check=True)
            time.sleep(1)
            subprocess.run(f'echo "{udc}" | sudo tee {udc_file}', shell=True, check=True)

        return {"status": "mounted", "iso": filename}

    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Mount failed: {e}")



@app.post("/stop")
def stop_usb_gadget():
    lun_file = "/sys/kernel/config/usb_gadget/composite_gadget/functions/mass_storage.usb0/lun.0/file"
    udc_file = "/sys/kernel/config/usb_gadget/composite_gadget/UDC"

    if not os.path.exists(lun_file):
        raise HTTPException(status_code=500, detail="Mass storage function not available")

    try:
        # Equivalent manual command:
        # echo "" | sudo tee /sys/kernel/config/usb_gadget/.../lun.0/file
        subprocess.run(
            f'echo "" | sudo tee {lun_file}',
            shell=True,
            check=True
        )

        # Rebind UDC to notify host
        if os.path.exists(udc_file):
            with open(udc_file, "r") as f:
                udc = f.read().strip()

            subprocess.run(f'echo "" | sudo tee {udc_file}', shell=True, check=True)
            time.sleep(1)
            subprocess.run(f'echo "{udc}" | sudo tee {udc_file}', shell=True, check=True)

        return {"status": "ejected", "message": "ISO unmounted successfully"}

    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Unmount failed: {e}")



@app.get("/", include_in_schema=False)
def serve_index():
    return FileResponse("templates/index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=9001)