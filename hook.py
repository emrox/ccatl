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
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

SETTINGS = Path.home() / ".claude" / "settings.json"
EVENTS = [  # (event, matcher, state) -- what install.sh writes into SETTINGS
    ("UserPromptSubmit", None, "busy"),
    ("PostToolUse", None, "busy"),
    ("PreToolUse", "AskUserQuestion|ExitPlanMode", "attention"),
    ("PermissionRequest", None, "attention"),
    ("Stop", None, "idle"),
    ("StopFailure", None, "idle"),
    ("SessionEnd", None, "gone"),
]
STATE = Path.home() / ".claude" / "traffic-light"
STALE = 8 * 3600  # a session killed without SessionEnd stops counting after this
IDLE_AFTER = 300  # untouched that long and a session counts as idle: cancelling a
                  # turn fires no hook at all. Raise it if a long single tool call
                  # (a slow build, a big test run) turns the light green too early.
COLORS = [("attention", "R"), ("busy", "Y")]  # first match wins, else green
VALID = {"busy", "attention", "idle", "gone"}


def payload():
    try:
        return json.loads(sys.stdin.read())
    except Exception:  # no stdin, truncated JSON, whatever: still worth a colour
        return {}


def aggregate():
    now = time.time()
    states = set()
    for f in STATE.glob("*.state"):
        try:
            age = now - f.stat().st_mtime
            if age > STALE:
                f.unlink()
                continue
            if age < IDLE_AFTER:
                states.add(f.read_text().strip())
        except OSError:  # another session pruned it first
            pass
    for state, color in COLORS:
        if state in states:
            return color
    return "G"


def ensure_keeper():
    """Keep one detached process sitting on the port.

    Every open of an unheld port reboots the Uno, which is the ~2 s of dark LEDs
    between colours; while a keeper holds it, a colour change takes ~10 ms. The
    keeper owns keeper.lock for as long as it lives, so a dead one (board
    unplugged, process killed) frees the lock and the next paint respawns it.
    """
    from light import find_port, hold

    lock_fd = os.open(str(STATE / "keeper.lock"), os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(lock_fd)  # somebody else is keeping the port open
        return
    # winning the lock means there was no keeper, so the board is freshly plugged
    # in or about to be reset by our own open: its LEDs are off, whatever the
    # cache says. Drop it so the next paint always writes.
    (STATE / "last").unlink(missing_ok=True)
    if os.fork():
        os.close(lock_fd)  # send() absorbs the reboot this fork is about to cause
        return
    os.setsid()
    try:
        hold(find_port(), tick=paint)  # holds port and keeper.lock until unplugged
    finally:
        os._exit(0)


def paint():
    from light import send

    ensure_keeper()  # before the lock below: a forked keeper must not inherit it
    with open(STATE / "lock", "w") as lock:
        for _ in range(50):  # bounded: a wedged painter must not pile up hooks behind it
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                time.sleep(0.1)
        else:
            return
        want = aggregate()  # recomputed inside the lock, so a queued write is never stale
        last = STATE / "last"
        if last.exists() and last.read_text() == want:
            return
        send(want)
        last.write_text(want)


def ours(command):
    """Our hook entries, in either the uv shebang form or the python3 one."""
    words = command.split()
    return any(w.endswith("hook.py") for w in words) and words[-1] in VALID


def command(state):
    """How settings.json should invoke us.

    With uv present the shebang handles the pyserial dependency itself; without
    it, fall back to whatever python3 is on PATH and hope pyserial is there.
    """
    me = str(Path(__file__).resolve())
    if shutil.which("uv"):
        return "%s %s" % (me, state)
    return "%s %s %s" % (shutil.which("python3") or sys.executable, me, state)


def strip(hooks):
    """Remove our entries from a settings hook table, whatever path they use."""
    for event in list(hooks):
        hooks[event] = [
            g for g in hooks[event]
            if not any(ours(h.get("command", "")) for h in g.get("hooks", []))
        ]
        if not hooks[event]:
            del hooks[event]


def edit_settings(install):
    """Add or remove the hooks in ~/.claude/settings.json, backup first."""
    settings = json.loads(SETTINGS.read_text()) if SETTINGS.exists() else {}
    if SETTINGS.exists():
        backup = SETTINGS.with_name("settings.json.bak-%s" % time.strftime("%Y%m%d%H%M%S"))
        backup.write_text(SETTINGS.read_text())
        print("backup: %s" % backup)
    hooks = settings.setdefault("hooks", {})
    strip(hooks)  # also clears an install from an older checkout
    if install:
        for event, matcher, state in EVENTS:
            group = {"hooks": [{"type": "command", "command": command(state)}]}
            if matcher:
                group["matcher"] = matcher
            hooks.setdefault(event, []).append(group)
    if not hooks:
        del settings["hooks"]
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS.write_text(json.dumps(settings, indent=2) + "\n")
    print("%s %d hooks in %s" % ("installed" if install else "removed",
                                 len(EVENTS), SETTINGS))
    if install and not shutil.which("uv"):
        print("uv not found, hooks will run under python3 --")
        if not importlib.util.find_spec("serial"):
            print("  pyserial is missing too: pip install pyserial")
    if not install:
        try:
            from light import send

            send("O")  # leave the board dark rather than stuck on a stale colour
        except Exception:
            pass
        # states only, so this never matches the uninstall process itself; by name
        # rather than full path, so a keeper started via a relative path still dies
        subprocess.run(["pkill", "-f", "hook.py (%s)" % "|".join(sorted(VALID))])
        shutil.rmtree(STATE, ignore_errors=True)
        print("stopped the keeper and removed %s" % STATE)
    print("restart running Claude Code sessions to pick this up")


def main(argv):
    if len(argv) > 1 and argv[1] in ("install", "uninstall"):
        return edit_settings(argv[1] == "install")
    if len(argv) < 2 or argv[1] not in VALID:
        sys.exit("usage: %s %s|install|uninstall" % (argv[0], "|".join(sorted(VALID))))
    STATE.mkdir(parents=True, exist_ok=True)
    state = argv[1]
    data = payload()
    log = STATE / "events.log"
    if log.exists() and log.stat().st_size > 200_000:
        log.unlink()
    with log.open("a") as f:
        f.write("%s %-9s %s\n" % (time.strftime("%H:%M:%S"), state, json.dumps(data)))
    marker = STATE / ((data.get("session_id") or "unknown") + ".state")
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
