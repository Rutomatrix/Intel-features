from fastapi import FastAPI, Query, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse
import subprocess
from fastapi.middleware.cors import CORSMiddleware
import os
import shutil
import time

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Target directory path on Raspberry Pi
TARGET_DIR = "/home/rpi/os"

# Ensure target directory exists
os.makedirs(TARGET_DIR, exist_ok=True)

# Allowed file extensions for security
ALLOWED_EXTENSIONS = {".iso", ".img"}

@app.post("/upload")
async def upload_os_image(file: UploadFile = File(...)):
    filename = file.filename
    if not filename:
        raise HTTPException(status_code=400, detail="No file selected mapping execution window context.")

    clean_filename = os.path.basename(filename)
    _, ext = os.path.splitext(clean_filename.lower())

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Only .iso and .img targets are permitted."
        )

    file_path = os.path.join(TARGET_DIR, clean_filename)

    try:
        # 1MB Memory buffering block prevents systemic OOM faults on Pi during long uploads
        CHUNKS_1MB = 1024 * 1024
        with open(file_path, "wb") as buffer:
            while chunk := await file.read(CHUNKS_1MB):
                buffer.write(chunk)

        return JSONResponse(status_code=200, content={
            "status": "success",
            "message": f"Successfully loaded asset parameters: {clean_filename}"
        })

    except Exception as e:
        # Handles user explicit cancel events cleanly, removing the partial dead data block
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass  # Avoid masking the main upload failure issue
        raise HTTPException(status_code=500, detail=f"Streaming closed: {str(e)}")

@app.get("/list")
async def list_isos():
    """
    Lists available ISO and IMG files inside the target directory.
    """
    try:
        files = [
            f for f in os.listdir(TARGET_DIR)
            if os.path.splitext(f.lower())[1] in ALLOWED_EXTENSIONS
        ]
        return {"available_isos": sorted(files)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read directory: {str(e)}")

# Keep your existing /mount and /stop routes below...

@app.post("/mount")
async def mount_os_image(filename: str):
    # Sanitize inputs to prevent directory traversal vulnerabilities
    clean_filename = os.path.basename(filename)
    file_path = os.path.join(TARGET_DIR, clean_filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"Target file target not found: {clean_filename}")

    try:
        # Insert your low-level setup logic here (e.g., echo path > /sys/kernel/config/usb_gadget/...)
        # execute_mount_subsystem(file_path)

        return {"status": "success", "iso": clean_filename}
    except Exception as e:
        # Fallback to prevent a raw 500 script crash dump
        raise HTTPException(status_code=500, detail=f"Mass storage engine failure: {str(e)}")



@app.post("/stop")
def stop_usb_gadget():
    lun_file = "/sys/kernel/config/usb_gadget/composite_gadget/functions/mass_storage.usb0/lun.0/file"
    udc_file = "/sys/kernel/config/usb_gadget/composite_gadget/UDC"

    if not os.path.exists(lun_file):
        raise HTTPException(status_code=500, detail="Mass storage function block not available")

    try:
        # 1. Truncate the LUN file directly to release the loop device backing file cleanly
        with open(lun_file, "w") as f:
            f.truncate(0)

        # 2. Safely cycle the UDC binding if it exists
        if os.path.exists(udc_file):
            with open(udc_file, "r") as f:
                udc_name = f.read().strip()

            if udc_name:
                # Disconnect the configuration matrix safely
                with open(udc_file, "w") as f:
                    f.write("\n")

                # Allow physical hardware layout a longer window to settle down
                time.sleep(1.5)

                # Rebind device controller array to announce state updates to Host PC
                with open(udc_file, "w") as f:
                    f.write(udc_name)

        return {"status": "ejected", "message": "ISO unmounted successfully"}

    except PermissionError:
        raise HTTPException(status_code=500, detail="Permission denied writing to sysfs parameters. Ensure your API runner has root/sudo rights.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sysfs unmount engine failure context: {str(e)}")


# ============================================================
# NEW DELETE ENDPOINT
# ============================================================
@app.delete("/delete")
async def delete_iso(filename: str = Query(..., description="Name of the ISO file to delete")):
    """
    Delete an ISO or IMG file from the target directory.
    """
    try:
        # Sanitize inputs to prevent directory traversal vulnerabilities
        clean_filename = os.path.basename(filename)

        # Security: Prevent directory traversal attacks
        if '..' in clean_filename or '/' in clean_filename or '\\' in clean_filename:
            raise HTTPException(status_code=400, detail="Invalid filename: Directory traversal not allowed")

        # Check file extension
        _, ext = os.path.splitext(clean_filename.lower())
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"File type '{ext}' not allowed. Only .iso and .img files can be deleted."
            )

        file_path = os.path.join(TARGET_DIR, clean_filename)

        # Check if file exists
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"File not found: {clean_filename}")

        # Check if it's a file (not a directory)
        if not os.path.isfile(file_path):
            raise HTTPException(status_code=400, detail=f"'{clean_filename}' is not a file")

        # Attempt to delete the file
        try:
            os.remove(file_path)
            return {
                "status": "success",
                "message": f"Successfully deleted: {clean_filename}",
                "deleted": clean_filename
            }
        except PermissionError:
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: Cannot delete {clean_filename}. Check file permissions."
            )
        except OSError as e:
            raise HTTPException(
                status_code=500,
                detail=f"OS error while deleting file: {str(e)}"
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@app.get("/", include_in_schema=False)
def serve_index():
    return FileResponse("templates/index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=9001)