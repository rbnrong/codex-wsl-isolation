#!/usr/bin/env python3
"""S3: clone the old WSL sqlite index into a new sqlite_home and rewrite rollout paths to ext4.

The old index is opened read-only and never modified. Dry run unless --apply.
Afterwards set `sqlite_home = "<new-sqlite>"` in ~/.codex/config.toml.
"""
import argparse, os, sqlite3, sys

ap = argparse.ArgumentParser()
ap.add_argument("--old-sqlite", required=True, help="old CODEX_SQLITE_HOME, e.g. ~/.codex/sqlite")
ap.add_argument("--new-sqlite", required=True, help="new sqlite_home, e.g. ~/.codex/sqlite-wsl")
ap.add_argument("--win-home", required=True, help="old Windows CODEX_HOME as seen from WSL, e.g. /mnt/c/Users/me/.codex")
ap.add_argument("--wsl-home", default=os.path.expanduser("~/.codex"))
ap.add_argument("--apply", action="store_true")
a = ap.parse_args()
old, new = os.path.expanduser(a.old_sqlite), os.path.expanduser(a.new_sqlite)
win = a.win_home.rstrip("/") + "/"
wsl = os.path.expanduser(a.wsl_home).rstrip("/") + "/"
DBS = ("state_5", "thread_history_1", "memories_1", "memories_v2_1", "goals_1", "queue_1")

src = sqlite3.connect(f"file:{old}/state_5.sqlite?mode=ro", uri=True)
rows = src.execute("select id, rollout_path from threads").fetchall()
rewrite = [r for r in rows if r[1].startswith(win)]

def exists(p):
    return os.path.exists(p) or os.path.exists(p + ".zst")

after = [(i, wsl + p[len(win):] if p.startswith(win) else p) for i, p in rows]
missing = [p for _, p in after if not exists(p)]
print(f"threads: {len(rows)}  rewrite {win} -> {wsl}: {len(rewrite)}  missing after rewrite: {len(missing)}")
for p in missing[:20]:
    print("  missing:", p)
if not a.apply:
    print("dry run; add --apply (missing transcripts were already missing or not yet copied by s1)")
    sys.exit()
if os.path.exists(new):
    sys.exit(f"refusing: {new} already exists")
os.makedirs(new)
for n in DBS:
    f = f"{old}/{n}.sqlite"
    if not os.path.exists(f):
        continue
    s = sqlite3.connect(f"file:{f}?mode=ro", uri=True)
    d = sqlite3.connect(f"{new}/{n}.sqlite")
    s.backup(d); d.close(); s.close()
c = sqlite3.connect(f"{new}/state_5.sqlite")
c.execute("update threads set rollout_path = ? || substr(rollout_path, ?) where rollout_path like ?",
          (wsl, len(win) + 1, win + "%"))
c.commit()
print("integrity:", c.execute("pragma integrity_check").fetchone()[0])
print(f'done. now add to ~/.codex/config.toml:  sqlite_home = "{new}"')
