#!/usr/bin/env bash
# Snapshot the WSL Codex host to another drive. Run before every desktop update, while codex is idle.
set -euo pipefail
DEST_ROOT="${CODEX_BACKUP_DEST:-/mnt/d/codex-backup-wsl}"
KEEP="${CODEX_BACKUP_KEEP:-5}"
H="$HOME/.codex"
SQL=$(grep -E '^sqlite_home' "$H/config.toml" 2>/dev/null | sed -E 's/.*"(.*)".*/\1/' || true)
SQL="${SQL:-$H}"
DEST="$DEST_ROOT/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$DEST/sqlite"
for db in "$SQL"/*.sqlite; do
  python3 - "$db" "$DEST/sqlite/$(basename "$db")" <<'PY'
import sqlite3, sys
s = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True); d = sqlite3.connect(sys.argv[2])
s.backup(d); d.close(); s.close()
PY
done
tar -C "$H" -cf "$DEST/codex-home.tar" --exclude="./$(basename "$SQL")" \
  --exclude=./.tmp --exclude=./tmp --exclude=./cache --exclude=./log \
  --exclude="./*.sqlite" --exclude="./*.sqlite-wal" --exclude="./*.sqlite-shm" .
( cd "$DEST" && sha256sum sqlite/* codex-home.tar > SHA256SUMS )
du -sh "$DEST"
ls -1d "$DEST_ROOT"/*/ | head -n -"$KEEP" | xargs -r rm -rf
echo "backup ok: $DEST"
