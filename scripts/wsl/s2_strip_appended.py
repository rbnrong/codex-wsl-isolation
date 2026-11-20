#!/usr/bin/env python3
"""S2: in the WSL copies, remove junk the updated desktop appended to old WSL transcripts.

When the updated desktop opened old WSL sessions on the Windows host it appended
`thread_settings_applied` events whose paths are Windows-mangled (C:\\home\\..., C:\\mnt\\...).

Default (safe): remove only those events, only if timestamp >= --cutoff.
--all-after-cutoff (aggressive): remove EVERY line with timestamp >= cutoff in rollouts created
before the cutoff. Only use this right after s1, before you continue any session on the WSL host,
otherwise you will cut real new turns.

Originals are saved under --save. Dry run unless --apply.
"""
import argparse, json, os, re, shutil

ap = argparse.ArgumentParser()
ap.add_argument("--cutoff", required=True, help="UTC ISO time of first launch after update, e.g. 2026-11-20T13:20:00")
ap.add_argument("--wsl-home", default=os.path.expanduser("~/.codex"))
ap.add_argument("--save", default=os.path.expanduser("~/codex-migration/s2-originals"))
ap.add_argument("--all-after-cutoff", action="store_true")
ap.add_argument("--apply", action="store_true")
a = ap.parse_args()

ts_re = re.compile(rb'^\{"timestamp":"([0-9T:\-\.]+)Z?"')
BAD = (b'C:\\\\home\\\\', b'C:\\\\mnt\\\\')  # JSON-escaped backslashes


def is_junk(line):
    m = ts_re.match(line)
    if not m or m.group(1).decode() < a.cutoff:
        return False
    if a.all_after_cutoff:
        return True
    return b'"thread_settings_applied"' in line and any(b in line for b in BAD)


hits = 0
for sub in ("sessions", "archived_sessions"):
    for dp, _, fs in os.walk(os.path.join(a.wsl_home, sub)):
        for f in fs:
            if not f.endswith(".jsonl"):
                continue
            p = os.path.join(dp, f)
            lines = open(p, "rb").read().splitlines(keepends=True)
            if not lines:
                continue
            m0 = ts_re.match(lines[0])
            if not m0 or m0.group(1).decode() >= a.cutoff:
                continue  # created after the update: leave alone
            keep = [l for l in lines if not is_junk(l)]
            drop = len(lines) - len(keep)
            if not drop:
                continue
            hits += 1
            print(f"{os.path.relpath(p, a.wsl_home)}: drop {drop} line(s)")
            if a.apply:
                rel = os.path.relpath(p, a.wsl_home)
                os.makedirs(os.path.dirname(os.path.join(a.save, rel)), exist_ok=True)
                shutil.copy2(p, os.path.join(a.save, rel))
                st = os.stat(p)
                open(p, "wb").write(b"".join(keep))
                os.utime(p, (st.st_atime, st.st_mtime))
mode = "aggressive" if a.all_after_cutoff else "safe"
print(f"[{mode}] files affected: {hits}", "(applied)" if a.apply else "(dry run; add --apply)")
