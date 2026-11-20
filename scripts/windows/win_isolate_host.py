"""Isolate the Windows (local) host from everything WSL.

1. MOVES (never deletes) the Windows host index + transcripts to --archive:
   state_5 / thread_history_1 / goals_1 / memories_1 / queue_1 / logs_2 (*.sqlite + -wal/-shm),
   session_index.jsonl, sessions\\, archived_sessions\\
2. config.toml: removes [projects."..."] blocks whose path starts with /home, /mnt or contains wsl,
   plus projectlessWorkspaceRoot=\\\\wsl... and git-worktree-root=/home/... (paths the Windows host
   cannot use). integratedTerminalShell is left alone: it only picks the terminal shell.
3. sqlite\\codex.db: deletes desktop catalog rows + sync state for host 'local' (rebuilt on launch)
4. .codex-global-state.json: drops remaining 'local' membership tags and projectless ids not in the catalog

Only do this once your WSL host has all the history (steps 1-3 of the README). Dry run unless --apply.
"""
import argparse, os, re, shutil, sqlite3, sys, time
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from _common import CODEX_HOME, CATALOG_DB, require_app_closed, load_state, save_state

ap = argparse.ArgumentParser()
ap.add_argument("--archive", required=True, help="folder on another drive, e.g. D:\\codex-archive")
ap.add_argument("--apply", action="store_true")
a = ap.parse_args()
if a.apply:
    require_app_closed()
dest = os.path.join(a.archive, "win-host-" + time.strftime("%Y%m%d-%H%M%S"))

# 1. index + transcripts
DBS = ("state_5", "thread_history_1", "goals_1", "memories_1", "queue_1", "logs_2")
items = [f"{n}.sqlite{s}" for n in DBS for s in ("", "-wal", "-shm")]
items += ["session_index.jsonl", "session_index.jsonl.lock", "sessions", "archived_sessions"]
items = [i for i in items if os.path.exists(os.path.join(CODEX_HOME, i))]
print("move to archive:", items)

# 2. config.toml
cfg_path = os.path.join(CODEX_HOME, "config.toml")
lines = open(cfg_path, encoding="utf-8").read().split("\n")
out, drop, removed = [], False, []
hdr = re.compile(r"^\[projects\.(\"([^\"]*)\"|'([^']*)')\]\s*$")
for l in lines:
    if l.startswith("["):
        m = hdr.match(l)
        p = (m.group(2) if m and m.group(2) is not None else (m.group(3) if m else None))
        drop = bool(p) and (p.startswith("/home/") or p.startswith("/mnt/") or "wsl" in p.lower())
        if drop:
            removed.append(l)
            continue
    if drop:
        continue
    st = l.strip()
    if (st.startswith("projectlessWorkspaceRoot") and "wsl" in st.lower()) or \
       (st.startswith("git-worktree-root") and "/home/" in st):
        removed.append(l)
        continue
    out.append(l)
new_cfg = re.sub(r"\n{3,}", "\n\n", "\n".join(out))
print(f"config.toml: remove {len(removed)} line(s)/block(s)")
for r in removed:
    print("   -", r)

# 3. catalog
cat_n = 0
if os.path.exists(CATALOG_DB):
    c = sqlite3.connect(CATALOG_DB)
    cat_n = c.execute("select count(*) from local_thread_catalog where host_id='local'").fetchone()[0]
    c.close()
print(f"codex.db: delete {cat_n} catalog row(s) for host 'local'")

# 4. state tags
s = load_state()
M = s.get("thread-project-membership-host-ids", {})
tags = [t for t, h in M.items() if h == "local"]
print(f"global state: drop {len(tags)} 'local' membership tag(s)")

if not a.apply:
    print("dry run; add --apply")
    sys.exit()

os.makedirs(dest)
shutil.copy2(cfg_path, os.path.join(dest, "config.toml"))
if os.path.exists(CATALOG_DB):
    os.makedirs(os.path.join(dest, "sqlite"))
    for f in os.listdir(os.path.dirname(CATALOG_DB)):
        if f.startswith("codex.db"):
            shutil.copy2(os.path.join(os.path.dirname(CATALOG_DB), f), os.path.join(dest, "sqlite", f))
for i in items:
    shutil.move(os.path.join(CODEX_HOME, i), os.path.join(dest, i))

import tomllib
tomllib.loads(new_cfg)
open(cfg_path + ".tmp", "w", encoding="utf-8", newline="\n").write(new_cfg)
os.replace(cfg_path + ".tmp", cfg_path)

if os.path.exists(CATALOG_DB):
    c = sqlite3.connect(CATALOG_DB)
    c.execute("delete from local_thread_catalog where host_id='local'")
    c.execute("delete from local_thread_catalog_sync_state where host_id='local'")
    c.commit()
    c.execute("pragma wal_checkpoint(TRUNCATE)")
    c.close()
    cat = {r[0] for r in sqlite3.connect(CATALOG_DB).execute("select thread_id from local_thread_catalog")}
else:
    cat = set()

for t in tags:
    del M[t]
if "projectless-thread-ids" in s:
    s["projectless-thread-ids"] = [t for t in s["projectless-thread-ids"] if t in cat]
save_state(s, "isolate-host")
print("archived to", dest)
