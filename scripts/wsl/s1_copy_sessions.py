#!/usr/bin/env python3
"""S1: copy session transcripts from the Windows CODEX_HOME to the WSL host's ~/.codex (ext4).

Never overwrites existing files. Dry run unless --apply.
"""
import argparse, os, shutil, sys

ap = argparse.ArgumentParser()
ap.add_argument("--win-home", required=True, help="Windows CODEX_HOME as seen from WSL, e.g. /mnt/c/Users/me/.codex")
ap.add_argument("--wsl-home", default=os.path.expanduser("~/.codex"))
ap.add_argument("--apply", action="store_true")
a = ap.parse_args()

plan = []
for sub in ("sessions", "archived_sessions"):
    src_root = os.path.join(a.win_home, sub)
    if not os.path.isdir(src_root):
        print(f"skip: {src_root} not found")
        continue
    for dp, _, fs in os.walk(src_root):
        for f in fs:
            src = os.path.join(dp, f)
            dst = os.path.join(a.wsl_home, sub, os.path.relpath(src, src_root))
            if not os.path.exists(dst):
                plan.append((src, dst))

size = sum(os.path.getsize(s) for s, _ in plan)
print(f"files to copy: {len(plan)}  ({size/1e6:.0f} MB)  -> {a.wsl_home}")
if not a.apply:
    print("dry run; add --apply")
    sys.exit()
for s, d in plan:
    os.makedirs(os.path.dirname(d), exist_ok=True)
    shutil.copy2(s, d)
    os.chmod(d, 0o644)
print("done")
