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
