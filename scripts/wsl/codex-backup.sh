#!/usr/bin/env bash
# Snapshot the WSL Codex host to another drive. Run before every desktop update, while codex is idle.
#
#   CODEX_BACKUP_DEST  where snapshots go (default /mnt/d/codex-backup-wsl). Use a DEDICATED folder:
#                      only completed timestamped snapshots are pruned.
#   CODEX_BACKUP_KEEP  how many snapshots to keep (default 5)
set -euo pipefail
DEST_ROOT="${CODEX_BACKUP_DEST:-/mnt/d/codex-backup-wsl}"
KEEP="${CODEX_BACKUP_KEEP:-5}"
case "$KEEP" in ''|*[!0-9]*) echo "CODEX_BACKUP_KEEP must be a number" >&2; exit 1 ;; esac
[ "$KEEP" -ge 1 ] 2>/dev/null || { echo "CODEX_BACKUP_KEEP must be a positive decimal integer in range" >&2; exit 1; }
KEEP=$((10#$KEEP))

H="$HOME/.codex"
SQL=$(grep -E '^[[:space:]]*sqlite_home[[:space:]]*=' "$H/config.toml" 2>/dev/null | head -n1 \
      | sed -E "s/^[^=]*=[[:space:]]*[\"']([^\"']*)[\"'].*/\1/" || true)
SQL="${SQL/#\~/$HOME}"
SQL="${SQL:-$H}"
[ -d "$SQL" ] || { echo "sqlite home not found: $SQL" >&2; exit 1; }

mkdir -p -- "$DEST_ROOT"
DEST_ROOT=$(cd -- "$DEST_ROOT" && pwd -P)
DEST="$DEST_ROOT/$(date +%Y%m%d-%H%M%S)"
STAGE=$(mktemp -d -- "$DEST_ROOT/.incomplete-XXXXXXXX")
trap 'rm -rf -- "$STAGE"' EXIT
mkdir -- "$STAGE/sqlite"
shopt -s nullglob
for db in "$SQL"/*.sqlite; do
  python3 - "$db" "$STAGE/sqlite/$(basename "$db")" <<'PY'
import sqlite3, sys
s = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True); d = sqlite3.connect(sys.argv[2])
s.backup(d); d.close(); s.close()
PY
done
shopt -u nullglob

EXCL=(--exclude=./.tmp --exclude=./tmp --exclude=./cache --exclude=./log
      --exclude="./*.sqlite" --exclude="./*.sqlite-wal" --exclude="./*.sqlite-shm")
case "$SQL" in "$H"/*) EXCL+=(--exclude="./${SQL#"$H"/}") ;; esac
tar -C "$H" -cf "$STAGE/codex-home.tar" "${EXCL[@]}" .
( cd -- "$STAGE" && sha256sum sqlite/* codex-home.tar > SHA256SUMS )
touch -- "$STAGE/.codex-backup-complete"
# Publish on the same filesystem without overwriting a run that used the same second.
mv -Tn -- "$STAGE" "$DEST"
if [[ -e "$STAGE" ]]; then
  echo "snapshot already exists: $DEST" >&2
  exit 1
fi
trap - EXIT
du -sh "$DEST"

# Older successful backups wrote SHA256SUMS last. Require a digest for the tar
# and each SQLite copy before counting an unmarked directory in retention.
is_complete_snapshot() (
  cd -- "$1" || exit 1
  [[ -s codex-home.tar && -s SHA256SUMS ]] || exit 1
  [[ -f .codex-backup-complete ]] && exit 0
  shopt -s nullglob
  local databases=(sqlite/*.sqlite)
  (( ${#databases[@]} > 0 )) || exit 1
  diff -q <(printf '%s\n' "${databases[@]}" codex-home.tar | LC_ALL=C sort) \
          <(sed -nE 's/^[0-9a-f]{64} [ *](.+)$/\1/p' SHA256SUMS | LC_ALL=C sort) >/dev/null
)

SNAPS=()
while IFS= read -r -d '' snapshot; do
  if is_complete_snapshot "$snapshot"; then
    SNAPS+=("$snapshot")
  fi
done < <(find "$DEST_ROOT" -mindepth 1 -maxdepth 1 -type d \
  -regextype posix-extended -regex '.*/[0-9]{8}-[0-9]{6}' -print0 | sort -z)
EXTRA=$(( ${#SNAPS[@]} - KEEP ))
for (( i = 0; i < EXTRA; i++ )); do
  rm -rf -- "${SNAPS[$i]}"
  echo "pruned: ${SNAPS[$i]}"
done
echo "backup ok: $DEST"
