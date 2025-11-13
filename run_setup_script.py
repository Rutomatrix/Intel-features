import os
import subprocess

def make_executable_and_run(script_path):
    # Check if the file exists
    if not os.path.exists(script_path):
        print(f"❌ Script not found: {script_path}")
        return

    # Make the file executable
    try:
        print(f"🔒 Making {script_path} executable...")
        os.chmod(script_path, 0o755)
        print("✅ File is now executable.")
    except PermissionError:
        print("⚠️ Permission denied. Try running this Python script with sudo.")
        return

    # Run the bash script
    print(f"🚀 Running the script: {script_path}")
    try:
        process = subprocess.Popen(
            ["bash", script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        # Stream live output to console
        for line in process.stdout:
            print(line, end="")

        process.wait()
        if process.returncode == 0:
            print("🎉 Script executed successfully!")
        else:
            print(f"❌ Script exited with return code: {process.returncode}")

    except Exception as e:
        print(f"⚠️ An error occurred while running the script: {e}")

if __name__ == "__main__":
    script_path = "./intel_rpi_setup.sh"  # Path to your bash script
    make_executable_and_run(script_path)
