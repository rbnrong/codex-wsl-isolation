#!/usr/bin/env bash
# Run the Codex desktop app's bundled WSL runtime as a CLI.
# Follows the "current" symlink so desktop updates are picked up automatically.
# --no-daemon is required: the bundled runtime ships without a standalone daemon package.
exec "$HOME/.local/share/codex/desktop-cli/public/current/codex" --no-daemon "$@"
