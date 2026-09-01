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


def main(argv):
    if len(argv) < 2 or argv[1] not in CMDS:
        sys.exit("usage: %s %s [port]" % (argv[0], "|".join(CMDS)))
    port = argv[2] if len(argv) > 2 else find_port()
    with serial.Serial(port, 9600, timeout=2) as link:
        time.sleep(2)  # opening the port asserts DTR, which resets the Uno
        link.write(CMDS[argv[1]].encode())
        print(link.readline().decode().strip() or "no ack from board")


if __name__ == "__main__":
    main(sys.argv)
