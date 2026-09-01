#!/bin/sh
# Point ~/.claude/settings.json at the hook.py next to this script.
dir=$(cd "$(dirname "$0")" && pwd)
if command -v uv >/dev/null 2>&1; then
  exec uv run --script "$dir/hook.py" install
fi
exec python3 "$dir/hook.py" install
