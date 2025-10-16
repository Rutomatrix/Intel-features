# Setup & Usage Guide

This guide walks you through installing and running the **Scripts API** service on your Raspberry Pi, and how to clone and execute your shell scripts with live, line-by-line output.

---

## 1) Place `setup.py` in `/home/rpi`

Copy your FastAPI app file (e.g., `setup.py`) into the following path:
```bash
/home/rpi/setup.py
```

> If your file is named differently (e.g., `scripts_api.py`), keep the same steps but update the filename in your service unit.

---

## 2) Create a Python virtual environment (in `/home/rpi`)

```bash
cd /home/rpi
python3 -m venv venv
```

---

## 3) Activate the virtual environment (in `/home/rpi`)

```bash
source venv/bin/activate
```

You should see `(venv)` in your shell prompt.

---

## 4) Install dependencies

```bash
python3 -m pip install fastapi uvicorn pydantic
```

> You can add more dependencies later if your app requires them.

---

## 5) Install and start the systemd service

1. Place your service unit file at:
   ```bash
   /etc/systemd/system/setup.service
   ```

   A typical `setup.service` might look like this (adjust paths if your file is not `setup.py`):
   ```ini
   [Unit]
   Description=Scripts API (FastAPI + Uvicorn)
   After=network.target
   Wants=network-online.target

   [Service]
   User=rpi
   Group=rpi
   WorkingDirectory=/home/rpi
   Environment=PYTHONUNBUFFERED=1
   ExecStart=/home/rpi/venv/bin/python -m uvicorn setup:app --host 0.0.0.0 --port 9010 --workers 1
   Restart=always
   RestartSec=3

   [Install]
   WantedBy=multi-user.target
   ```

2. Reload, enable, and start the service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now setup.service
   ```

---

## 6) Check service status

```bash
sudo systemctl status setup.service
```

> Use `q` to exit the status view. For live logs:
> ```bash
> sudo journalctl -u setup.service -f
> ```

---

## 7) Clone the `scripts/` folder (first-time setup)

The API needs to clone the `scripts` folder from your Git repository on first use.

---

## 8) Clone via API call

Use `curl` to trigger the sparse-clone of the `scripts` directory:
```bash
curl -X POST http://127.0.0.1:9010/scripts/clone
```

> If your API requires a JSON body, you can use:
> ```bash
> curl -X POST http://127.0.0.1:9010/scripts/clone >   -H "Content-Type: application/json" -d '{}'
> ```

After cloning, your scripts should be in:
```
/home/rpi/scripts
```

---

## 9) Test the run routes (streaming)

Run the following to execute scripts with **live, line-by-line output**:

```bash
curl -N -X POST "http://127.0.0.1:9010/scripts/run/streaming_hid/stream"
curl -N -X POST "http://127.0.0.1:9010/scripts/run/remove_streaming_hid/stream"
```

> Tip: `-N` tells `curl` not to buffer the streamed output.

---

## 10) Live output

When invoked via the `/stream` endpoints, the API relays the process output **exactly as the script prints it**, so you can watch progress in real time in your terminal.

---

### Notes & Troubleshooting

- If your scripts use `apt-get`, `systemctl`, or other privileged commands, run the API as **root** or configure **passwordless sudo** for those scripts.
- If your service runs as root but you want to use `/home/rpi` paths, set the environment variable `SCRIPT_USER=rpi` in your service unit and adjust the working directory accordingly.
- Ensure your scripts are executable (`chmod +x /home/rpi/scripts/*.sh`). The clone step usually sets this automatically.

---

**Done!** You can now manage your scripts via the REST API and watch their output live.
