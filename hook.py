#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyserial"]
# ///
"""Claude Code hook: colour the traffic light from the state of every session.

    hook.py busy|attention|idle|gone      < hook JSON on stdin

One file per session under ~/.claude/traffic-light/ holds that session's state.
Red beats yellow beats green: any session waiting on the user makes it red, any
session working makes it yellow, otherwise green.

The serial write happens in a detached child so a hook never delays Claude Code,
and a flock plus a cached last colour keeps concurrent sessions from fighting
over the port or repainting a colour that is already showing.
"""

import fcntl
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from light import send  # noqa: E402

STATE = Path.home() / ".claude" / "traffic-light"
STALE = 8 * 3600  # a session killed without SessionEnd stops counting after this
COLORS = [("attention", "R"), ("busy", "Y")]  # first match wins, else green
VALID = {"busy", "attention", "idle", "gone"}


def session_id():
    try:
        return json.load(sys.stdin).get("session_id") or "unknown"
    except Exception:  # no stdin, truncated JSON, whatever: still worth a colour
        return "unknown"


def aggregate():
    now = time.time()
    states = set()
    for f in STATE.glob("*.state"):
        try:
            if now - f.stat().st_mtime > STALE:
                f.unlink()
                continue
            states.add(f.read_text().strip())
        except OSError:  # another session pruned it first
            pass
    for state, color in COLORS:
        if state in states:
            return color
    return "G"


def paint():
    with open(STATE / "lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        want = aggregate()  # recomputed inside the lock, so a queued write is never stale
        last = STATE / "last"
        if last.exists() and last.read_text() == want:
            return
        send(want)
        last.write_text(want)


def main(argv):
    if len(argv) < 2 or argv[1] not in VALID:
        sys.exit("usage: %s %s" % (argv[0], "|".join(sorted(VALID))))
    STATE.mkdir(parents=True, exist_ok=True)
    state = argv[1]
    marker = STATE / (session_id() + ".state")
    if state == "gone":
        marker.unlink(missing_ok=True)
    else:
        marker.write_text(state)

    if os.fork():
        return  # parent hands control straight back to Claude Code
    os.setsid()
    devnull = os.open(os.devnull, os.O_RDWR)
    for fd in (0, 1, 2):
        os.dup2(devnull, fd)
    try:
        paint()
    except Exception:
        pass  # an unplugged board must never break a session
    os._exit(0)


if __name__ == "__main__":
    main(sys.argv)
