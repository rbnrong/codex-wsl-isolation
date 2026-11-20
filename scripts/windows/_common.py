"""Shared helpers for the Windows-side scripts. Run with Windows Python: py -I script.py"""
import json, os, shutil, subprocess, sys, time

CODEX_HOME = os.environ.get("CODEX_HOME_WIN", os.path.join(os.path.expanduser("~"), ".codex"))
STATE = os.path.join(CODEX_HOME, ".codex-global-state.json")
CATALOG_DB = os.path.join(CODEX_HOME, "sqlite", "codex.db")
WSL_PREFIXES = ("\\\\wsl$\\", "\\\\wsl.localhost\\")


def require_app_closed():
    out = subprocess.run(["tasklist", "/FO", "CSV"], capture_output=True, text=True, errors="ignore").stdout.lower()
    if "chatgpt.exe" in out or '"codex.exe"' in out:
        sys.exit("The Codex/ChatGPT desktop app is still running. Quit it from the tray icon first.")


def wsl_path(p):
    """\\\\wsl$\\Ubuntu\\home\\me\\x -> ('Ubuntu', '/home/me/x'); None if not a WSL UNC path."""
    for pre in WSL_PREFIXES:
        if p.lower().startswith(pre.lower()):
            rest = p[len(pre):]
            distro, _, tail = rest.partition("\\")
            return distro, "/" + tail.replace("\\", "/")
    return None


def load_state():
    if not os.path.exists(STATE):
        sys.exit(f"not found: {STATE}")
    return json.load(open(STATE, encoding="utf-8"))


def save_state(s, tag):
    backup = f"{STATE}.pre-{tag}-{time.strftime('%Y%m%d-%H%M%S')}"
    shutil.copy2(STATE, backup)
    tmp = STATE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(s, ensure_ascii=False, separators=(",", ":")))
    json.load(open(tmp, encoding="utf-8"))
    os.replace(tmp, STATE)
    shutil.copy2(STATE, STATE + ".bak")  # keep the app's own .bak in sync or it may roll back
    print(f"written. previous version saved as {backup}")


def owner_atoms_key(s):
    return next((k for k in s if k.startswith("electron-owner-atoms")), None)
