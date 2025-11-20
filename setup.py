from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import os
import shlex
import subprocess
import asyncio
import json
from typing import List, Optional, Dict, Any

app = FastAPI(title="Scripts Manager")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # tighten for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Config ----
REPO_URL_DEFAULT = "https://github.com/Rutomatrix/Intel-features"
BRANCH_DEFAULT = "main"
SCRIPT_USER = os.environ.get("SCRIPT_USER", "rpi")  # Which home to use even if service runs as root
HOME = f"/home/{SCRIPT_USER}"
SCRIPTS_SUBDIR = "scripts"
TARGET_DIR = f"{HOME}/{SCRIPTS_SUBDIR}"            # e.g., /home/rpi/scripts

# If your API runs as non-root and you want to sudo the scripts, set SUDO=1 in the environment.
SUDO_PREFIX = "sudo " if os.environ.get("SUDO", "0") in ("1", "true", "yes") else ""

# Whitelist ONLY the required scripts
ALLOWED_SCRIPTS: Dict[str, str] = {
    "os_flashing": "os_flashing.sh",
    "remove_os_flashing": "remove_os_flashing.sh",
    "streaming_hid": "streaming_hid.sh",
    "remove_streaming_hid": "remove_streaming_hid.sh",
    "rpi_cfg": "rpi_cfg.sh",
    "install_postcode": "install_postcode.sh",
    "remove_postcode": "remove_postcode.sh",
}

# ---- Models ----
class CloneRequest(BaseModel):
    repo_url: Optional[str] = None
    branch: Optional[str] = None
    clean: bool = True  # remove existing /home/<user>/scripts before clone

# ---- Utilities ----
def run_cmd(cmd: str, cwd: Optional[str] = None) -> subprocess.CompletedProcess:
    """Runs a shell command and returns CompletedProcess (never raises)."""
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

def ensure_repo_file(repo_url: str, branch: str, relpath: str, dest_path: str):
    """
    Sparse-checkout a single file (relpath) from repo and copy to dest_path.
    """
    tmp = "/tmp/singlefile_sparse"
    subprocess.run(f"rm -rf {shlex.quote(tmp)}", shell=True, check=False)
    subprocess.run(f"mkdir -p {shlex.quote(tmp)}", shell=True, check=True)

    steps = [
        "git init",
        f"git remote add origin {shlex.quote(repo_url)}",
        f"git fetch --depth 1 origin {shlex.quote(branch)}",
        "git sparse-checkout init --cone",
        f"git sparse-checkout set {shlex.quote(relpath)}",
        f"git checkout {shlex.quote(branch)}",
    ]
    for s in steps:
        cp = run_cmd(s, cwd=tmp)
        if cp.returncode != 0:
            raise RuntimeError(f"[git singlefile] {s}\nstdout:\n{cp.stdout}\nstderr:\n{cp.stderr}")

    src = os.path.join(tmp, relpath)
    if not os.path.isfile(src):
        raise RuntimeError(f"File '{relpath}' not found in repo.")
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    subprocess.run(f"cp -f {shlex.quote(src)} {shlex.quote(dest_path)}", shell=True, check=True)

    try:
        user = SCRIPT_USER
        subprocess.run(f"chown {shlex.quote(user)}:{shlex.quote(user)} {shlex.quote(dest_path)}",
                       shell=True, check=False)
        subprocess.run(f"chmod 0644 {shlex.quote(dest_path)}", shell=True, check=False)
    except Exception:
        pass


def sparse_clone_scripts(repo_url: str, branch: str, dest_dir: str) -> None:
    """
    Sparse-checkout only the 'scripts' folder from repo into dest_dir,
    ending with files in /home/<user>/scripts.
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
    src_dir = f"{tmp}/{SCRIPTS_SUBDIR}"
    if not os.path.isdir(src_dir):
        raise RuntimeError("Sparse checkout succeeded but 'scripts' folder not found in repo.")

    os.makedirs(parent, exist_ok=True)
    subprocess.run(f"rm -rf {shlex.quote(dest_dir)}", shell=True, check=False)
    cp_cmd = f"cp -r {shlex.quote(src_dir)} {shlex.quote(dest_dir)}"
    subprocess.run(cp_cmd, shell=True, check=True)

    # ownership + exec bits
    try:
        user = SCRIPT_USER
        subprocess.run(
            f"chown -R {shlex.quote(user)}:{shlex.quote(user)} {shlex.quote(dest_dir)}",
            shell=True, check=False
        )
    except Exception:
        pass

    # ensure executables for all .sh in /home/<user>/scripts
    for name in os.listdir(dest_dir):
        if name.endswith(".sh"):
            ensure_executable(os.path.join(dest_dir, name))

def _script_path_for_key(key: str) -> str:
    if key not in ALLOWED_SCRIPTS:
        raise HTTPException(status_code=400, detail=f"Unknown script key '{key}'")
    script_path = os.path.join(TARGET_DIR, ALLOWED_SCRIPTS[key])
    if not os.path.isfile(script_path):
        raise HTTPException(status_code=404, detail=f"Script not found: {script_path}")
    return script_path

def _read_script_source(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception as e:
        return f"<unable to read script: {e}>"

# ---- Blocking run (returns full stdout/stderr; no source by default) ----
def run_script_by_key(key: str, args: Optional[List[str]] = None, include_source: bool = False) -> Dict[str, Any]:
    script_path = _script_path_for_key(key)
    ensure_executable(script_path)

    arg_str = " ".join(shlex.quote(a) for a in (args or []))
    cmd = f"{SUDO_PREFIX}/bin/bash {shlex.quote(script_path)} {arg_str}".strip()
    cp = subprocess.run(
        f"stdbuf -oL -eL {cmd}",
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        executable="/bin/bash",
    )
    result = {
        "script": key,
        "path": script_path,
        "args": args or [],
        "returncode": cp.returncode,
        "stdout": cp.stdout,
        "stderr": cp.stderr,
    }
    if include_source:
        result["script_source"] = _read_script_source(script_path)
    return result

# ---- Async streaming (robust, line-by-line, raw) ----
async def _stream_proc_raw(cmd: str, cwd: Optional[str]):
    """
    Spawn the process and stream stdout+stderr line-by-line with NO prefixes,
    exactly what the script prints. Reads as text and drains to EOF.
    """
    full_cmd = f"stdbuf -oL -eL {cmd}"
    proc = await asyncio.create_subprocess_shell(
        full_cmd,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,  # merge stderr into stdout
        executable="/bin/bash",
    )

    assert proc.stdout is not None
    while True:
        chunk = await proc.stdout.readline()
        if not chunk:
            break
        yield chunk.decode("utf-8", errors="replace")

    await proc.wait()

async def _stream_proc_with_format(cmd: str, cwd: Optional[str], fmt: str):
    if fmt == "plain":
        async for s in _stream_proc_raw(cmd, cwd):
            yield s
        return

    async for s in _stream_proc_raw(cmd, cwd):
        clean = s.rstrip("\n")  # <-- compute outside the f-string
        if fmt == "jsonl":
            yield json.dumps({"line": clean}) + "\n"
        else:  # sse
            yield "data: " + json.dumps({"line": clean}) + "\n\n"


# ---- Routes ----
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
def clone_scripts(req: Optional[CloneRequest] = Body(None)):
    repo = (req.repo_url if req and req.repo_url else REPO_URL_DEFAULT)
    branch = (req.branch if req and req.branch else BRANCH_DEFAULT)
    clean = (req.clean if req is not None else True)

    if clean and os.path.isdir(TARGET_DIR):
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
    args: Optional[List[str]] = Query(default=None, description="Optional args, e.g. ?args=foo&args=bar"),
    include_source: bool = Query(default=False, description="Include script file contents in the response"),
):
    result = run_script_by_key(key, args=args, include_source=include_source)
    if result["returncode"] != 0:
        raise HTTPException(status_code=500, detail=result)
    return result

@app.post("/scripts/run/{key}/stream")
async def run_named_script_stream(
    key: str,
    args: Optional[List[str]] = Query(default=None, description="Optional args, e.g. ?args=foo&args=bar"),
    format: str = Query(default="plain", pattern="^(plain|jsonl|sse)$",
                        description="Streaming format: plain (default), jsonl, or sse"),
):
    script_path = _script_path_for_key(key)
    ensure_executable(script_path)
    arg_str = " ".join(shlex.quote(a) for a in (args or []))
    cmd = f"{SUDO_PREFIX}/bin/bash {shlex.quote(script_path)} {arg_str}".strip()

    media = "text/plain"
    if format == "jsonl":
        media = "application/x-ndjson"
    elif format == "sse":
        media = "text/event-stream"

    async def gen():
        async for chunk in _stream_proc_with_format(cmd, cwd=None, fmt=format):
            yield chunk
        if format == "plain":
            yield ""

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Connection": "close",
    }
    return StreamingResponse(gen(), media_type=media, headers=headers)

@app.post("/rpi/config/apply/stream")
async def rpi_config_apply_stream(
    format: str = Query(default="plain", pattern="^(plain|jsonl|sse)$")
):
    dest_cfg = f"{HOME}/config.txt"
    try:
        ensure_repo_file(REPO_URL_DEFAULT, BRANCH_DEFAULT, "config.txt", dest_cfg)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fetching config.txt failed: {e}")

    script_path = _script_path_for_key("rpi_cfg")
    ensure_executable(script_path)
    # No args (script defaults): uses /home/<user>/config.txt, enables serial, reboots
    cmd = f"{SUDO_PREFIX}/bin/bash {shlex.quote(script_path)}"

    media = "text/plain"
    if format == "jsonl":
        media = "application/x-ndjson"
    elif format == "sse":
        media = "text/event-stream"

    async def gen():
        # helper to format a single line according to the chosen format
        def _fmt(line: str) -> str:
            if format == "plain":
                return line
            clean = line.rstrip("\n")  # <-- precompute
            if format == "jsonl":
                return json.dumps({"line": clean}) + "\n"
            # sse
            return "data: " + json.dumps({"line": clean}) + "\n\n"

        # 1) stream the config script output first
        async for chunk in _stream_proc_with_format(cmd, cwd=None, fmt=format):
            yield chunk

        # 2) after the script exits, run verification commands (if the Pi hasn't rebooted yet)
        # NOTE: if the script reboots the Pi, the connection will drop before these run.
        yield _fmt("\n# Verification: Check UART enabled in config\n")
        uart_cmd = r"grep -E '^enable_uart=' /boot/firmware/config.txt || grep -E '^enable_uart=' /boot/config.txt"
        cp1 = run_cmd(uart_cmd)
        out1 = (cp1.stdout or "") + (cp1.stderr or "")
        if out1.strip():
            for line in out1.splitlines(True):
                yield _fmt(line)
        else:
            yield _fmt("(no enable_uart line found)\n")

        yield _fmt("\n# Verification: Check serial login shell (serial-getty) status\n")
        getty_cmd = "systemctl status serial-getty@ttyAMA0.service || systemctl status serial-getty@ttyS0.service"
        cp2 = run_cmd(getty_cmd)
        out2 = (cp2.stdout or "") + (cp2.stderr or "")
        for line in out2.splitlines(True):
            yield _fmt(line)

        if format == "plain":
            # final newline helps curl finish cleanly
            yield ""

    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "close"}
    return StreamingResponse(gen(), media_type=media, headers=headers)



# ---- Convenience shortcuts (only the four required) ----
@app.post("/scripts/run/os_flashing")
def run_os_flashing():
    return run_named_script("os_flashing")

@app.post("/scripts/run/remove_os_flashing")
def run_remove_os_flashing():
    return run_named_script("remove_os_flashing")

@app.post("/scripts/run/streaming_hid")
def run_streaming_hid():
    return run_named_script("streaming_hid")

@app.post("/scripts/run/remove_streaming_hid")
def run_remove_streaming_hid():
    return run_named_script("remove_streaming_hid")

@app.post("/scripts/run/install_postcode")
def run_postcode():
    return run_named_script("install_postcode")

@app.post("/scripts/run/remove_postcode")
def run_remove_postcode():
    return run_named_script("remove_postcode")

@app.get("/")
def root():
    return {
        "message": "Scripts API ready",
        "home": HOME,
        "target_dir": TARGET_DIR,
        "clone": {"POST": "/scripts/clone"},
        "list": {"GET": "/scripts/list"},
        "run": {
            "POST /scripts/run/{key}": list(ALLOWED_SCRIPTS.keys()),
            "POST /scripts/run/{key}/stream": "stream live output (plain/jsonl/sse)",
            "shortcuts": [
                "/scripts/run/os_flashing",
                "/scripts/run/remove_os_flashing",
                "/scripts/run/streaming_hid",
                "/scripts/run/remove_streaming_hid",
                "/scripts/run/install_postcode",             
                "/scripts/run/remove_postcode",
            ],
        },
    }
