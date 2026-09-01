#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyserial"]
# ///
"""Switch the Arduino traffic light over USB serial."""

import glob
import os
import sys
import time

import serial

CMDS = {"red": "R", "yellow": "Y", "green": "G", "off": "O"}
PATTERNS = ("/dev/cu.usbmodem*", "/dev/ttyACM*")
BOOT = 1.8  # bootloader delay after a reset; raise if the first write is lost


def find_port():
    ports = sorted(p for pat in PATTERNS for p in glob.glob(pat))
    if not ports:
        sys.exit("no Arduino found (looked for %s)" % ", ".join(PATTERNS))
    return ports[0]


def send(char, port=None):
    """Send one command byte and return the board's ack (empty string if none).

    Opening the port asserts DTR, which reboots the Uno and swallows the byte --
    unless another process already holds the port open, in which case the write
    lands in about 10 ms. So try the fast path first and only pay for the
    bootloader when the ack goes missing. See hold().
    """
    with serial.Serial(port or find_port(), 9600, timeout=0.3) as link:
        link.write(char.encode())
        ack = link.readline()
        if not ack:
            time.sleep(BOOT)
            link.timeout = 2
            link.write(char.encode())
            ack = link.readline()
        return ack.decode().strip()


def hold(port=None, tick=None, every=5):
    """Keep the port open until the board goes away, so nothing resets it.

    tick() runs every `every` seconds while holding. That is the only clock in
    the system: without it, state no event ever reports -- an interrupted turn,
    say -- would sit on the board until the next hook happens to fire.
    """
    port = port or find_port()
    with serial.Serial(port, 9600, timeout=1):
        while os.path.exists(port):
            if tick:
                tick()
            time.sleep(every)


def main(argv):
    if len(argv) < 2 or argv[1] not in CMDS:
        sys.exit("usage: %s %s [port]" % (argv[0], "|".join(CMDS)))
    port = argv[2] if len(argv) > 2 else find_port()
    print(send(CMDS[argv[1]], port) or "no ack from board")


if __name__ == "__main__":
    main(sys.argv)
