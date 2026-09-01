#!/bin/sh
# Remove the hooks, darken the LEDs, stop the keeper, drop the state dir.
dir=$(cd "$(dirname "$0")" && pwd)
if command -v uv >/dev/null 2>&1; then
  exec uv run --script "$dir/hook.py" uninstall
fi
exec python3 "$dir/hook.py" uninstall
