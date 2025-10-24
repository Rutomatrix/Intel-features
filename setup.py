from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import os
import shlex
import subprocess
import asyncio
import json
from typing import List, Optional, Dict, Any, AsyncGenerator

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

# Whitelist the scripts you want to expose (key -> filename)
ALLOWED_SCRIPTS: Dict[str, str] = {
    "os_flashing": "os_flashing.sh",
    "remove_os_flashing": "remove_os_flashing.sh",
    "remove_streaming_hid": "remove_streaming_hid.sh",
    "streaming_hid": "streaming_hid.sh",
}

# ---- Models ----
class CloneRequest(BaseModel):
    repo_url: Optional[str] = None
    branch: Optional[str] = None
    clean: bool = True  # remove existing /home/<user>/scripts before clone

class RunRequest(BaseModel):
    args: Optional[List[str]] = None
    include_source: bool = False   # default False per your preference

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

# ---- Blocking run (returns full stdout/stderr; source optional) ----
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

    # Read as text line-by-line (decode manually for robustness)
    # NOTE: asyncio doesn't support text=True, so decode bytes -> str here.
    assert proc.stdout is not None
    while True:
        chunk = await proc.stdout.readline()
        if not chunk:
            break
        # decode bytes safely
        yield chunk.decode("utf-8", errors="replace")

    # ensure the process has fully exited
    await proc.wait()


async def _stream_proc_with_format(cmd: str, cwd: Optional[str], fmt: str):
    if fmt == "plain":
        async for s in _stream_proc_raw(cmd, cwd):
            # s already ends with newline when produced by script
            yield s
        return

    # jsonl or sse formats
    async for s in _stream_proc_raw(cmd, cwd):
        line = s.rstrip("\n")
        if fmt == "jsonl":
            yield json.dumps({"line": line}) + "\n"
        else:  # sse
            yield f"data: {json.dumps({'line': line})}\n\n"



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

    # optional clean
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
    """
    Run a whitelisted script by key. Returns JSON with complete stdout/stderr (after completion).
    """
    result = run_script_by_key(key, args=args, include_source=include_source)
    if result["returncode"] != 0:
        # Still return everything, but as HTTP 500 for clients that rely on status code
        raise HTTPException(status_code=500, detail=result)
    return result

@app.post("/scripts/run/{key}/stream")
async def run_named_script_stream(
    key: str,
    args: Optional[List[str]] = Query(default=None, description="Optional args, e.g. ?args=foo&args=bar"),
    format: str = Query(default="plain", pattern="^(plain|jsonl|sse)$",
                        description="Streaming format: plain (default), jsonl, or sse"),
):
    """
    Stream live output EXACTLY like terminal (default = plain).
    """
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
        # stream the command (no headers/timestamps)
        async for chunk in _stream_proc_with_format(cmd, cwd=None, fmt=format):
            yield chunk
        # flush a final newline, helps curl not complain
        if format == "plain":
            yield ""

    # add headers that help proxies/clients not buffer/guess sizes
    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",  # Nginx
        "Connection": "close",
    }
    return StreamingResponse(gen(), media_type=media, headers=headers)

# Convenience shortcuts (no args)
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
                "/scripts/run/remove_streaming_hid",
                "/scripts/run/streaming_hid",
            ],
        },
    }
