# 🧠 Intel RPI Setup

This repository includes an automated setup process for configuring a Raspberry Pi with all required dependencies, configuration files, and service setups related to the **Intel-features** project.

---

## 🚀 How to Run the Setup

To begin the setup, simply run the following command from the project root:

```bash
python run_setup_script.py
```

## ⚙️ What This Process Does

Running the setup script performs the following tasks in order:

### 1️⃣ Verify Git Installation
- Checks whether **Git** is installed on the Raspberry Pi.  
- If not installed, automatically installs Git using `apt`.

---

### 2️⃣ Clone the Repository
- Clones the repository:  
  👉 [https://github.com/Rutomatrix/Intel-features.git](https://github.com/Rutomatrix/Intel-features.git)  
  into `/home/rpi/Intel-features`.
- If the repository already exists, it performs a `git pull` to update the local copy.

---

### 3️⃣ Move Service Files
- Copies all `.service` files from the `service files/` folder inside the cloned repo  
  → to the system directory `/etc/systemd/system/`.
- These service files define the system services that will **auto-start on boot**.

---

### 4️⃣ Make Bash Files Executable
- Searches the entire project directory for all `.sh` files.  
- Makes them executable using `chmod +x`.

---

### 5️⃣ Run Dependency Scripts
- Executes each `.sh` file found in the `dependencies/` folder.  
- These scripts usually handle installing or configuring **third-party packages** required by the project.

---

### 6️⃣ Run Configuration Scripts
- Executes all `.sh` files from the `configs/` folder.  
- These scripts typically configure **environment variables**, **application settings**, or **device-specific parameters**.

---

### 7️⃣ Enable and Start System Services
- Reloads the **systemd** daemon.  
- Enables and starts all services copied to `/etc/systemd/system/`.  
- If any service requires a reboot, the system will **automatically restart**.

---

## 1. USB File Sharing Setup

This setup uses a Python application with **Flask** to enable file sharing when a USB drive is inserted.

### Pre-requirements

Before running the application, ensure the following tools and libraries are installed and configured:

### Running the File Sharing Application

1.  Place the `usb_file_sharing.py` file in the destination directory where you intend to insert the USB drive.


2.  **Python:**
    * Verify installation:
        ```bash
        python --version
        pip --version
        ```
        If not installed, then install python first and verify it.

3.  **File Format:**
    * The Python file **must** have a `.py` extension, not `.py.txt`.
    * If your file is named `app.py.txt`, rename it using the command below (replace `app.py.txt` and `app.py` with your actual file names):
        ```bash
        cd <dir_name>
        mv app.py.txt app.py
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

5.  Run the Python file (replace `app.py` with your actual file name):
    ```bash
    python app.py
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
3.  **Automate the setup:** Need to automate the usb_file_sharing.py file setup in the destination device
4.  **Automate the whole process:** Need to automate the whole process of the cloning the repo inside the RPI and start all the services