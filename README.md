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

# Raspberry Pi Feature Setup Guide

This guide details the steps required to set up **USB File Sharing** and install **System Drivers** (excluding the USB File Sharing component) on a Raspberry Pi.

---

## 1. USB File Sharing Setup

This setup uses a Python application with **Flask** to enable file sharing when a USB drive is inserted.

### Pre-requirements

Before running the application, ensure the following tools and libraries are installed and configured:

### Pre-requirements: Install Git

First, ensure **Git** is installed on the destination device:

1.  Verify if Git is installed:
    ```bash
    git --version
    ```
2.  If Git is not installed, follow these steps:
    * Update the package index:
        ```bash
        sudo apt update
        ```
    * Install Git:
        ```bash
        sudo apt install git -y
        ```
    * Verify installation again:
        ```bash
        git --version
        ```

### Running the File Sharing Application

1.  Place the `usb_file_sharing.py` file in the destination directory where you intend to insert the USB drive. Use below command in the command promt (Destination device's cmd). Open the directory where you want to store the file in the cmd.
      ```bash
      cd <directory name>

      curl -o usb_file_sharing.py https://raw.githubusercontent.com/Rutomatrix/Intel-features/main/usb_file_sharing.py
      ```


2.  **Python:**
    * Verify installation:
        ```bash
        python --version
        pip --version
        ```
        If not installed, then install python first and verify it.

3.  **File Format:**
    * The Python file **must** have a `.py` extension, not `.py.txt`.
    * If your file is named `usb_file_sharing.py.txt`, rename it using the command below (replace `usb_file_sharing.py.txt` and `usb_file_sharing.py` with your actual file names):
        ```bash
        cd <dir_name>
        mv usb_file_sharing.py.txt usb_file_sharing.py
        ```

4.  **Python Libraries:**
    * Install the required libraries: **Flask**, **Flask-Cors**, and **Waitress**.
        ```bash
        pip install Flask Flask-Cors waitress
        ```
    * Verify installation:
        ```bash
        pip show Flask Flask-Cors waitress
        ```

5.  Run the Python file:
    ```bash
    python usb_file_sharing.py
    ```
---

## 2. System Drivers Installation (Excluding USB File Sharing)

This section covers cloning a repository and installing service files for additional drivers/features.

### Pre-requirements: Install Git

First, ensure **Git** is installed on the Raspberry Pi:

1.  Verify if Git is installed:
    ```bash
    git --version
    ```
2.  If Git is not installed, follow these steps:
    * Update the package index:
        ```bash
        sudo apt update
        ```
    * Install Git:
        ```bash
        sudo apt install git -y
        ```
    * Verify installation again:
        ```bash
        git --version
        ```

### Clone and Install Drivers

1.  **Navigate** to the home directory for the `rpi` user:
    ```bash
    cd /home/rpi
    ```
2.  **Clone** the feature repository. This will create a local folder (e.g., `Intel-features`):
    ```bash
    git clone https://github.com/Rutomatrix/Intel-features.git
    ```
3.  **Copy** the necessary service files to the system's `systemd` directory:
    ```bash
    sudo cp -r intel-features/service-files/* /etc/systemd/system/
    ```

4.  **Reboot** the Raspberry Pi to apply the service changes:
    ```bash
    sudo reboot
    ```

Once the RPI has rebooted, all the installed features and drivers should be accessible.

---

## 3. Future Development (Yet to Do)

The following items are planned for future development:

1.  **Static IP Management:** Implement a global variable to store the **static IP address** and utilize it across all drivers where required.
2.  **Static IP Driver:** Develop a dedicated driver to display and manage the configured static IP address.