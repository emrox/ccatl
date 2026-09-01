#!/bin/sh
# Remove the traffic-light hooks, stop the keeper, drop the state directory.
exec "$(cd "$(dirname "$0")" && pwd)/hook.py" uninstall
