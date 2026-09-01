#!/bin/sh
# Point ~/.claude/settings.json at the hook.py sitting next to this script.
exec "$(cd "$(dirname "$0")" && pwd)/hook.py" install
