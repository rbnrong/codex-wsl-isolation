"""Repoint thread->project assignments from old local \\\\wsl$ projects to the matching WSL remote projects,
then remove those local projects and stale 'local' membership / projectless tags.

Run win_add_remote_projects.py --apply first. Dry run unless --apply. Quit the desktop app first.
Threads that the desktop explicitly marked as projectless but whose cwd matches a WSL remote project
are NOT auto-assigned (they will be matched by cwd once the projectless tag is gone).
"""
import sys
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from _common import require_app_closed, load_state, save_state, wsl_path, owner_atoms_key

apply = "--apply" in sys.argv
if apply:
    require_app_closed()
s = load_state()
for k in ("local-projects", "remote-projects", "thread-project-assignments"):
    if k not in s:
        sys.exit(f"unexpected state format: missing '{k}'")

remote = {(p["hostId"], p["remotePath"]): p["id"] for p in s["remote-projects"]}
LP = s["local-projects"]
mapping = {}
for pid, p in LP.items():
    roots = p.get("rootPaths") or []
    if p.get("chatGptBacking") or len(roots) != 1:
        continue
    w = wsl_path(roots[0])
    if not w:
        continue
    rid = remote.get((f"remote-wsl:{w[0]}", w[1]))
    if not rid:
        sys.exit(f"no WSL remote project for {p['name']} ({w[1]}); run win_add_remote_projects.py --apply first")
    mapping[pid] = (rid, f"remote-wsl:{w[0]}")
    print(f"  {p['name']}: local {pid[:12]} -> remote {rid[:8]}")

A = s["thread-project-assignments"]
M = s.get("thread-project-membership-host-ids", {})
PL = s.get("projectless-thread-ids", [])
moves = [t for t, v in A.items() if v.get("projectKind") == "local" and v.get("projectId") in mapping]
tags = [t for t in moves if M.get(t) == "local"]
print(f"assignments to repoint: {len(moves)}; 'local' tags to drop: {len(tags)}; local projects to remove: {len(mapping)}")
if not apply:
    print("dry run; add --apply")
    sys.exit()

for t in moves:
    rid, host = mapping[A[t]["projectId"]]
    A[t] = {"projectKind": "remote", "projectId": rid, "hostId": host}
for t in tags:
    del M[t]
SO = s.get("sidebar-project-thread-orders", {})
dead = set()
for pid, (rid, _) in mapping.items():
    if pid in SO:
        SO.setdefault(rid, SO.pop(pid))
    del LP[pid]
    dead.add("codex:project:" + pid)
s["project-order"] = [x for x in s.get("project-order", []) if x not in mapping]
ak = owner_atoms_key(s)
if ak:
    uo = s[ak].get("unified-sidebar-project-order-v1")
    if isinstance(uo, list):
        s[ak]["unified-sidebar-project-order-v1"] = [x for x in uo if x not in dead]
    for acct in (s[ak].get("sidebar-custom-sections-v3") or {}).values():
        for sec in acct.get("sections", []):
            sec["itemKeys"] = [x for x in sec.get("itemKeys", []) if x not in dead]
save_state(s, "repoint-assignments")
