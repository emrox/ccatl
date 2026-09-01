#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyserial"]
# ///
"""Switch the Arduino traffic light over USB serial."""

import glob
import sys
import time

import serial

CMDS = {"red": "R", "yellow": "Y", "green": "G", "off": "O"}
PATTERNS = ("/dev/cu.usbmodem*", "/dev/ttyACM*")


def find_port():
    ports = sorted(p for pat in PATTERNS for p in glob.glob(pat))
    if not ports:
        sys.exit("no Arduino found (looked for %s)" % ", ".join(PATTERNS))
    return ports[0]


def send(char, port=None, wait=2.0):
    """Send one command byte and return the board's ack (empty string if none)."""
    with serial.Serial(port or find_port(), 9600, timeout=2) as link:
        # ponytail: opening the port asserts DTR, which resets the Uno and costs
        # ~2 s of dark LEDs. A 10 uF cap between RESET and GND kills the
        # auto-reset; then wait can drop to 0.
        time.sleep(wait)
        link.write(char.encode())
        return link.readline().decode().strip()


def main(argv):
    if len(argv) < 2 or argv[1] not in CMDS:
        sys.exit("usage: %s %s [port]" % (argv[0], "|".join(CMDS)))
    port = argv[2] if len(argv) > 2 else find_port()
    print(send(CMDS[argv[1]], port) or "no ack from board")


if __name__ == "__main__":
    main(sys.argv)
