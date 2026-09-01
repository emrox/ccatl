# atl — USB traffic light

Three LEDs on an Arduino Uno Rev3 SMD, switched from the computer over USB serial.

## Wiring

```
D2 ──[220Ω]──▶|── red LED    ──┐
D3 ──[220Ω]──▶|── yellow LED ──┤
D4 ──[220Ω]──▶|── green LED  ──┤
                               └── GND (any Arduino GND pin)
```

Per LED:

1. Long leg (anode, `+`) through a 220 Ω resistor to its digital pin.
2. Short leg (cathode, `−`, flat spot on the rim) to the breadboard ground rail.
3. Ground rail to any Arduino `GND` pin.

- The resistor is not optional: a bare LED on 5 V pulls well past the 40 mA
  absolute maximum of a pin. Either side of the LED is fine, series is series.
- 220 Ω comes from `R = (5 V − 2.0 V) / 15 mA` = 200 Ω, rounded to the nearest
  standard value. If one colour looks too bright, swap that LED's resistor for
  330 Ω or 470 Ω — brightness is a resistor change, not a code change.
- D0/D1 carry the USB serial link and D13 has the onboard LED that toggles
  during the bootloader, hence D2–D4.

## Firmware

Open `traffic_light/traffic_light.ino` in the Arduino IDE, pick *Arduino Uno*
and the `/dev/cu.usbmodem*` port, upload.

Protocol: one uppercase byte, `R`, `Y`, `G`, or `O` (all off). The board echoes
the byte back as an ack. Anything else is ignored.

## Host

```sh
uv run light.py red
uv run light.py yellow
uv run light.py green
uv run light.py off
uv run light.py red /dev/cu.usbmodem14201   # explicit port
```

`light.py` declares pyserial inline (PEP 723), so `uv run` builds and caches the
environment on the first call — no venv to create, nothing to install by hand.
The shebang is `uv run --script`, so `./light.py red` works the same way.

Without uv: `pip install pyserial` (the package is `pyserial`, not `serial`),
then `./light.py red`.

The port is auto-detected from `/dev/cu.usbmodem*` (macOS) or `/dev/ttyACM*`
(Linux). Opening the port resets the Uno, so the script waits 2 s before
sending — that delay is why a single command takes a couple of seconds.

## Checking it works

1. Board unpowered: confirm every short leg reaches the ground rail and every
   long leg reaches its pin through a resistor.
2. Serial Monitor at 9600 baud, send `R`, `Y`, `G`, `O`. Exactly one LED should
   light and the byte should echo back. Ack but no light means that LED is in
   backwards — flip it.
3. `./light.py red`, then the other three commands.

## Claude Code hook

`hook.py` drives the light from the state of every running Claude Code session:

| Colour | Meaning |
| --- | --- |
| green | every session is idle |
| yellow | at least one session is working |
| red | at least one session wants you (question, plan approval, permission prompt) |

Red beats yellow beats green. Each session keeps one file under
`~/.claude/traffic-light/`, named by its session id, and the colour is the
highest-priority state present.

Cancelling a turn fires no hook, so a session that goes quiet for
`hook.IDLE_AFTER` (5 min) counts as idle, and the keeper re-evaluates every 5 s
— that is what eventually clears a cancelled turn even though nothing reported
it. `StopFailure` clears it immediately when Claude Code does report the
interrupt. Markers are deleted outright after 8 h.

Already merged into `~/.claude/settings.json` (backup alongside it as
`settings.json.bak-*`). The seven entries:

```json
{
  "hooks": {
    "UserPromptSubmit":  [{"hooks": [{"type": "command", "command": "/path/to/script/hook.py busy"}]}],
    "PostToolUse":       [{"hooks": [{"type": "command", "command": "/path/to/script/hook.py busy"}]}],
    "PreToolUse":        [{"matcher": "AskUserQuestion|ExitPlanMode",
                           "hooks": [{"type": "command", "command": "/path/to/script/hook.py attention"}]}],
    "PermissionRequest": [{"hooks": [{"type": "command", "command": "/path/to/script/hook.py attention"}]}],
    "Stop":              [{"hooks": [{"type": "command", "command": "/path/to/script/hook.py idle"}]}],
    "StopFailure":       [{"hooks": [{"type": "command", "command": "/path/to/script/hook.py idle"}]}],
    "SessionEnd":        [{"hooks": [{"type": "command", "command": "/path/to/script/hook.py gone"}]}]
  }
}
```

`PreToolUse` on `AskUserQuestion` is what makes red immediate, and
`PermissionRequest` covers permission prompts. `PostToolUse` turns red back to
yellow: once you answer, the next tool call proves the session is working again.

**Not `Notification`.** It looks like the obvious red trigger and it is a trap:
besides permission prompts it also fires the "waiting for your input" nudge
after ~60 s, so an instance sitting at an empty prompt paints the light red
while doing nothing, and no later event in that session ever clears it. It is
redundant anyway — measured, `PreToolUse` and `PermissionRequest` both land ~6 s
earlier.

Every hook fire is appended to `~/.claude/traffic-light/events.log` with its
payload (dropped past 200 kB). That log is what identified the stray red above:
the marker holding it belonged to a different session id than the one doing the
work.

The hook writes its state file, then forks a detached child for the serial
write, so it never adds latency to a turn. Concurrent sessions serialise on a
`flock`, and a cached last colour means a repeated state costs nothing.

Test it by hand:

```sh
echo '{"session_id":"test"}' | ./hook.py attention   # red
echo '{"session_id":"test"}' | ./hook.py gone        # back to green
```

### Why colour changes are fast

Opening the serial port asserts DTR, which reboots the Uno: on its own, every
colour change would cost ~2 s of dark LEDs. While *any* process holds the port
open, further opens no longer reset the board, so the first paint forks a
keeper that does nothing but sit on the port. Measured: 2.1 s for the first
change, 50-80 ms for every one after it.

The keeper doubles as the system's only clock: every 5 s it recomputes the
colour, which is how a cancelled turn or any other missed event heals itself.

The keeper owns `~/.claude/traffic-light/keeper.lock` for as long as it lives.
Unplug the board and it exits, releasing the lock; the next colour change
respawns it and pays the 2 s once more. `send()` needs no coordination with it
— a missing ack means the board is rebooting, so it waits `light.BOOT` and
resends.
