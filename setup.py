from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import shlex
import subprocess
from typing import List, Optional

app = FastAPI(title="Scripts Manager")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

REPO_URL_DEFAULT = "https://github.com/Rutomatrix/Intel-features"
BRANCH_DEFAULT = "main"
SCRIPTS_SUBDIR = "scripts"
HOME = f"/home/{os.environ.get('SUDO_USER') or os.environ.get('USER') or 'rpi'}"
TARGET_DIR = f"{HOME}/{SCRIPTS_SUBDIR}"  # /home/rpi/scripts

# Whitelist the scripts you want to expose
ALLOWED_SCRIPTS = {
    "os_flashing": "os_flashing.sh",
    "remove_os_flashing": "remove_os_flashing.sh",
    "remove_streaming_hid": "remove_streaming_hid.sh",
    "streaming_hid": "streaming_hid.sh",
}

class CloneRequest(BaseModel):
    repo_url: Optional[str] = None
    branch: Optional[str] = None
    clean: bool = True  # remove existing /home/rpi/scripts before clone

class RunRequest(BaseModel):
    args: Optional[List[str]] = None  # optional args to pass to the script


def run_cmd(cmd: str, cwd: Optional[str] = None) -> subprocess.CompletedProcess:
    """
    Runs a shell command and returns CompletedProcess (never raises).
    """
    return subprocess.run(
        cmd,
        shell=True,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def ensure_executable(path: str) -> None:
    try:
        st = os.stat(path)
        os.chmod(path, st.st_mode | 0o111)  # add +x
    except FileNotFoundError:
        pass


def sparse_clone_scripts(repo_url: str, branch: str, dest_dir: str) -> None:
    """
    Sparse-checkout only the 'scripts' folder from repo into dest_dir's parent,
    ending with files in /home/rpi/scripts.
    """
    parent = os.path.dirname(dest_dir) or "/"
    tmp = "/tmp/scripts_sparse_clone"

    # prep
    subprocess.run(f"rm -rf {shlex.quote(tmp)}", shell=True, check=False)
    subprocess.run(f"mkdir -p {shlex.quote(tmp)}", shell=True, check=True)

    # sparse checkout
    steps = [
        "git init",
        f"git remote add origin {shlex.quote(repo_url)}",
        f"git fetch --depth 1 origin {shlex.quote(branch)}",
        "git sparse-checkout init --cone",
        f"git sparse-checkout set {shlex.quote(SCRIPTS_SUBDIR)}",
        f"git checkout {shlex.quote(branch)}"
    ]
    for s in steps:
        cp = run_cmd(s, cwd=tmp)
        if cp.returncode != 0:
            raise RuntimeError(f"[git] {s}\nstdout:\n{cp.stdout}\nstderr:\n{cp.stderr}")

    # copy out the scripts folder
    if not os.path.isdir(f"{tmp}/{SCRIPTS_SUBDIR}"):
        raise RuntimeError("Sparse checkout succeeded but 'scripts' folder not found in repo.")
    # create parent and copy
    os.makedirs(parent, exist_ok=True)
    subprocess.run(f"rm -rf {shlex.quote(dest_dir)}", shell=True, check=False)
    cp_cmd = f"cp -r {shlex.quote(tmp)}/{SCRIPTS_SUBDIR} {shlex.quote(dest_dir)}"
    subprocess.run(cp_cmd, shell=True, check=True)

    # ownership + exec bits
    try:
        user = os.environ.get("SUDO_USER") or os.environ.get("USER") or "rpi"
        subprocess.run(f"chown -R {shlex.quote(user)}:{shlex.quote(user)} {shlex.quote(dest_dir)}",
                       shell=True, check=False)
    except Exception:
        pass

    # ensure executables for all .sh in /home/rpi/scripts
    for name in os.listdir(dest_dir):
        if name.endswith(".sh"):
            ensure_executable(os.path.join(dest_dir, name))


def run_script_by_key(key: str, args: Optional[List[str]] = None):
    """
    Run one of the whitelisted scripts by key (e.g., 'os_flashing').
    Returns dict with exit code, stdout, stderr.
    """
    if key not in ALLOWED_SCRIPTS:
        raise HTTPException(status_code=400, detail=f"Unknown script key '{key}'")

    script_path = os.path.join(TARGET_DIR, ALLOWED_SCRIPTS[key])
    if not os.path.isfile(script_path):
        raise HTTPException(status_code=404, detail=f"Script not found: {script_path}")

    ensure_executable(script_path)
    arg_str = " ".join(shlex.quote(a) for a in (args or []))
    cmd = f"/bin/bash {shlex.quote(script_path)} {arg_str}".strip()
    cp = run_cmd(cmd)
    return {
        "script": key,
        "path": script_path,
        "args": args or [],
        "returncode": cp.returncode,
        "stdout": cp.stdout,
        "stderr": cp.stderr,
    }


@app.get("/scripts/list")
def list_scripts():
    files = []
    if os.path.isdir(TARGET_DIR):
        for f in sorted(os.listdir(TARGET_DIR)):
            if f.endswith(".sh"):
                p = os.path.join(TARGET_DIR, f)
                files.append({
                    "name": f,
                    "path": p,
                    "executable": os.access(p, os.X_OK)
                })
    return {
        "target_dir": TARGET_DIR,
        "allowed_keys": list(ALLOWED_SCRIPTS.keys()),
        "found": files
    }


@app.post("/scripts/clone")
def clone_scripts(req: CloneRequest):
    repo = req.repo_url or REPO_URL_DEFAULT
    branch = req.branch or BRANCH_DEFAULT

    # optional clean
    if req.clean and os.path.isdir(TARGET_DIR):
        subprocess.run(f"rm -rf {shlex.quote(TARGET_DIR)}", shell=True, check=False)

    try:
        sparse_clone_scripts(repo, branch, TARGET_DIR)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Clone failed: {e}")

    return {
        "status": "ok",
        "repo": repo,
        "branch": branch,
        "target_dir": TARGET_DIR,
        "files": os.listdir(TARGET_DIR) if os.path.isdir(TARGET_DIR) else []
    }


@app.post("/scripts/run/{key}")
def run_named_script(
    key: str,
    args: Optional[List[str]] = Query(default=None, description="Optional args, e.g. ?args=foo&args=bar")
):
    """
    Run a whitelisted script by key: os_flashing, remove_os_flashing, remove_streaming_hid, streaming_hid
    """
    result = run_script_by_key(key, args=args)
    if result["returncode"] != 0:
        raise HTTPException(status_code=500, detail=result)
    return result


# Convenience dedicated routes (no args)
@app.post("/scripts/run/os_flashing")
def run_os_flashing():
    return run_named_script("os_flashing")

@app.post("/scripts/run/remove_os_flashing")
def run_remove_os_flashing():
    return run_named_script("remove_os_flashing")

@app.post("/scripts/run/remove_streaming_hid")
def run_remove_streaming_hid():
    return run_named_script("remove_streaming_hid")

@app.post("/scripts/run/streaming_hid")
def run_streaming_hid():
    return run_named_script("streaming_hid")


@app.get("/")
def root():
    return {
        "message": "Scripts API ready",
        "clone": {"POST": "/scripts/clone"},
        "list": {"GET": "/scripts/list"},
        "run": {
            "POST /scripts/run/{key}": list(ALLOWED_SCRIPTS.keys()),
            "shortcuts": [
                "/scripts/run/os_flashing",
                "/scripts/run/remove_os_flashing",
                "/scripts/run/remove_streaming_hid",
                "/scripts/run/streaming_hid",
            ],
        },
        "target_dir": TARGET_DIR,
    }
