"""Create WSL remote projects that mirror your old local \\\\wsl$\\... projects.

Reads `local-projects` in .codex-global-state.json; for every non-ChatGPT local project whose single
root is a WSL UNC path, adds an entry to `remote-projects` with hostId remote-wsl:<distro>, the same
label, and the Linux path. Skips paths that already have a WSL remote project.
Dry run unless --apply. Quit the desktop app first.
"""
import sys, uuid
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from _common import require_app_closed, load_state, save_state, wsl_path, owner_atoms_key

apply = "--apply" in sys.argv
if apply:
    require_app_closed()
s = load_state()
for k in ("local-projects", "remote-projects", "project-order"):
    if k not in s:
        sys.exit(f"unexpected state format: missing '{k}'")

existing = {(p["hostId"], p["remotePath"]) for p in s["remote-projects"]}
new = []
for pid, p in s["local-projects"].items():
    roots = p.get("rootPaths") or []
    if p.get("chatGptBacking") or len(roots) != 1:
        continue
    w = wsl_path(roots[0])
    if not w:
        continue
    host = f"remote-wsl:{w[0]}"
    if (host, w[1]) in existing:
        print(f"  exists : {p['name']}  {w[1]}")
        continue
    existing.add((host, w[1]))
    new.append({"id": str(uuid.uuid4()), "hostId": host, "remotePath": w[1], "label": p["name"]})
    print(f"  add    : {p['name']}  {host}  {w[1]}")

print(f"remote projects to add: {len(new)}")
if not apply or not new:
    print("dry run; add --apply" if not apply else "nothing to do")
    sys.exit()
s["remote-projects"].extend(new)
s["project-order"][0:0] = [n["id"] for n in new]
ak = owner_atoms_key(s)
if ak and isinstance(s[ak].get("unified-sidebar-project-order-v1"), list):
    s[ak]["unified-sidebar-project-order-v1"][0:0] = ["codex:project:" + n["id"] for n in new]
save_state(s, "add-remote-projects")
