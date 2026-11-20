# codex-wsl-isolation

**Recover and isolate legacy WSL-agent sessions after the Codex desktop app (Windows) moved WSL to "remote connections".**

> Unofficial and community-made. Not affiliated with OpenAI. Tested on Codex desktop **26.1117.31558** (MSIX `OpenAI.Codex_26.1117.3838.0`) with bundled CLI **0.171.0-alpha.13**, Ubuntu on WSL 2.
> These scripts edit undocumented internal state. **Back up first, read the dry-run output, then apply.**

[中文说明见下方](#中文说明)

---

## Who is this for

You used the Codex desktop app on Windows with **Agent environment = WSL** (`runCodexInWindowsSubsystemForLinux = true`). After the update that introduced **Settings → Connections → WSL** you see one or more of:

- Old sessions fail with `cannot restore workspace root /home/... on this host: path is not absolute`.
- Opening an old WSL session from the local (Windows) sidebar runs it in `C:\home\...` and appends wrong-path settings to the transcript.
- The dialog **"This installation cannot switch yet"** on every launch ("ChatGPT-linked projects and synced automations cannot move to WSL connections yet").
- `WSL: Ubuntu` connection shows `login-required`, or connects with an **empty** history and no projects.
- Some sessions show only partially.

Related upstream reports: openai/codex#62686, openai/codex#62735, openai/codex#61598, openai/codex#60054, openai/codex#28094.

## Why it breaks

Before the update the WSL agent used the **Windows** `C:\Users\<you>\.codex` as `CODEX_HOME` (via `/mnt/c/...`), usually with `CODEX_SQLITE_HOME` on WSL ext4. After the update:

| | Windows host (`local`) | WSL host (`remote-wsl:<distro>`) |
|---|---|---|
| CODEX_HOME | `C:\Users\<you>\.codex` | `~/.codex` (fresh, empty) |
| Runtime | `%LOCALAPPDATA%\OpenAI\Codex\bin\<hash>\codex.exe` | `~/.local/share/codex/desktop-cli/public/current/codex` |
| Index | rebuilt from the old **WSL** rollouts it found in `C:\...\.codex\sessions` | empty |

So the Windows host adopted every WSL session (and runs them with Windows paths), while the WSL host knows nothing. The desktop's own project/assignment state (`.codex-global-state.json`) still points those sessions at local `\\wsl$\...` projects.

## The fix in one picture

```
before                                   after
Windows .codex  ── sessions (WSL!) ─┐    Windows .codex   (empty index, Windows-only)
                └─ index (WSL!)     │
WSL ~/.codex    ── empty            │    WSL ~/.codex     sessions + sqlite-wsl + config
WSL old sqlite  ── 700+ threads ────┘                     (all old WSL history, ext4)
desktop state   ── \\wsl$ local projects  desktop state  WSL remote projects, assignments repointed
```

Principle: **the WSL host owns everything that ran under WSL; the Windows host owns nothing from WSL.** After that, future desktop updates have much less shared state to break.

## Before you start

- **Quit the desktop app completely** (tray icon → Quit). Check: `tasklist | findstr /i "ChatGPT codex"` is empty. Otherwise it rewrites the state files on exit.
- `wsl --shutdown` before the big copy steps.
- **Back up**: `C:\Users\<you>\.codex`, WSL `~/.codex` (and your old sqlite home), and `%LOCALAPPDATA%\Packages\OpenAI.Codex_*\LocalCache\Roaming\Codex`. A tar + robocopy to another drive is fine.
- The migration scripts in steps 1–4 default to **dry run**. Add `--apply` to write changes. The backup command in step 5 immediately writes a snapshot and prunes old backups. Windows-side scripts (`win_*.py`) run with Windows Python (`py -I script.py`), WSL-side scripts run inside WSL.

## Steps

### 0. Log in the WSL host with the bundled runtime (no extra CLI install)

```bash
~/.local/share/codex/desktop-cli/public/current/codex login --device-auth
```

Optional convenience wrapper so `codex` works in your WSL shell (the bundled runtime needs `--no-daemon`):

```bash
install -m 755 scripts/wsl/codex-wrapper.sh ~/.local/bin/codex
```

### 1. Copy session transcripts to WSL ext4 and strip post-update junk (WSL)

```bash
python3 scripts/wsl/s1_copy_sessions.py --win-home /mnt/c/Users/<you>/.codex            # dry run
python3 scripts/wsl/s1_copy_sessions.py --win-home /mnt/c/Users/<you>/.codex --apply
python3 scripts/wsl/s2_strip_appended.py --cutoff 2026-11-20T13:20:00                    # dry run; cutoff = update time (UTC)
python3 scripts/wsl/s2_strip_appended.py --cutoff 2026-11-20T13:20:00 --apply
```

`s2` (safe default) only removes `thread_settings_applied` events with Windows-mangled paths (`C:\home\…`, `C:\mnt\…`) that were written after the cutoff, in files created before it. Originals are saved. `--all-after-cutoff` removes every post-cutoff line; use it only right after `s1` and before you continue any session on the WSL host. Pick the cutoff = when you first launched the updated app (desktop log: first `[wsl-migration] ... stage=started`, UTC).

### 2. Clone the old index and point it at ext4 (WSL)

```bash
python3 scripts/wsl/s3_clone_index.py --old-sqlite ~/.codex/sqlite --new-sqlite ~/.codex/sqlite-wsl \
        --win-home /mnt/c/Users/<you>/.codex            # dry run, then --apply
```

Then add to `~/.codex/config.toml` (top-level):

```toml
sqlite_home = "/home/<you>/.codex/sqlite-wsl"
```

Copy over what the WSL host should share with your old setup: `AGENTS.md`, user `skills/` (not `.system`), `memories/`, `memories_v2/`, model/sandbox keys and `[projects."/home/..."] trust_level = "trusted"`. **Do not** copy Windows-only keys (`[windows]`, `[desktop]`, `notify`, `mcp_servers.node_repl`, `marketplaces`).

Check: `codex doctor` shows `sqlite home ~/.codex/sqlite-wsl`, and `codex resume <id>` opens an old session.

> Forked/attached sessions write new turns into their **source** rollout. Copy whole trees, not single files, or resume fails with `invalid paginated history lineage ... missing source rollout`.

### 3. Fix the desktop sidebar (Windows, app quit)

```powershell
py -I scripts\windows\win_add_remote_projects.py            # creates WSL remote projects mirroring your \\wsl$ local projects
py -I scripts\windows\win_add_remote_projects.py --apply
py -I scripts\windows\win_repoint_assignments.py            # repoint thread→project assignments, drop "local" tags
py -I scripts\windows\win_repoint_assignments.py --apply
```

These edit `C:\Users\<you>\.codex\.codex-global-state.json` and keep `.codex-global-state.json.bak` in sync (otherwise the app may roll back).

### 4. Isolate the Windows host (Windows, app quit)

```powershell
py -I scripts\windows\win_isolate_host.py --archive D:\codex-archive            # dry run
py -I scripts\windows\win_isolate_host.py --archive D:\codex-archive --apply
```

Moves (not deletes) the Windows host index (`state_5`, `thread_history_1`, ... + wal/shm), `session_index.jsonl`, `sessions\`, `archived_sessions\` to the archive; removes `/home`, `/mnt`, `\\wsl$` project-trust entries plus `projectlessWorkspaceRoot` / `git-worktree-root` values that point into WSL; deletes the desktop catalog rows for host `local` in `sqlite\codex.db`. `integratedTerminalShell` is left as is (it only chooses the terminal shell). On next launch the Windows host starts with an empty index; ChatGPT-linked projects re-sync from the cloud.

### 5. Backup before every update (WSL)

```bash
install -m 755 scripts/wsl/codex-backup.sh ~/.local/bin/codex-backup
CODEX_BACKUP_DEST=/mnt/d/codex-backup-wsl codex-backup
```

Use a **dedicated** folder for `CODEX_BACKUP_DEST`. After the SQLite copies, tar archive and checksum manifest are written, the script publishes the snapshot under a name such as `20261121-040321`. An interrupted backup does not use a retention slot. Older, unmarked timestamp directories count only if their manifest lists a digest for the tar archive and every copied SQLite database. The script keeps the newest `CODEX_BACKUP_KEEP` completed snapshots (default 5). This is a positive decimal count, so `010` keeps ten and `08` keeps eight.

## Known limitations

- The "cannot switch yet" dialog still appears on launch; click **Set up later**.
- The sidebar may lazy-load; sessions with only `.zst` transcripts sometimes show late. They resume fine from CLI.
- Desktop state format is internal and may change in any release. Scripts refuse to run if expected keys are missing.
- WSL-side plugins (documents/spreadsheets/...) are not migrated; install them in the WSL connection when needed.
- `s3_clone_index.py` rewrites only `threads.rollout_path`, which is what resume needs. Other stored paths keep pointing at the old Windows home (`/mnt/c/.../.codex`): writable roots inside `threads.sandbox_policy`, an occasional `cwd` such as `.codex/pets`, and roots of ChatGPT-linked projects in `project_roots`. These are historical metadata and did not affect loading or continuing sessions in testing; a resumed session applies the current sandbox settings.
- A transcript that only exists as `.zst` resumes fine; the CLI's `resume` picker may hide sessions with `has_user_event = 0`, use `codex resume <id>`.

## Restore

Every script writes its originals next to the archive (or `*.pre-*` copies). To undo: quit the app, put the backed-up files back.

---

## 中文说明

**适用场景**：Windows 版 Codex 桌面端原来把 Agent 环境设为 WSL，更新到"WSL 远程连接"版本后出现以下问题：

- 旧会话打不开，报 `path is not absolute`；
- 在本机入口打开会话，工作目录变成 `C:\home`；
- 每次启动都弹"当前安装实例暂时无法切换"；
- WSL 连接下是空的。

**原因**：过去 WSL agent 和 Windows 共用 `C:\...\.codex`，新版把两者拆成两个独立主机。Windows 主机把原本属于 WSL 的会话正文"收养"了，WSL 主机却是全新的空目录，桌面端的项目归属也还指向旧的 `\\wsl$` 本机项目。

**思路**：凡是在 WSL 里跑出来的会话，全部归 WSL 主机：把正文复制到 ext4，克隆旧索引并改写路径，再用 `sqlite_home` 指过去。Windows 主机不再保留任何 WSL 内容：归档它的索引，清理 config 和桌面端状态。两边隔离开以后，后续更新能影响的范围小得多。

**注意事项**：

- 每一步之前都要完全退出桌面端，包括托盘里的进程，并先做备份。
- 第 1–4 步的迁移脚本默认只演练（dry run），确认输出后加 `--apply` 写入更改。第 5 步的备份命令会立即写入快照，并按 `CODEX_BACKUP_KEEP` 轮换已完成的备份。失败的备份不占保留名额。
- 本方案只在上面列出的版本上验证过。

## License

MIT
