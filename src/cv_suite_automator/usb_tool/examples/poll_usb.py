#!/usr/bin/env python3
"""
usb_enum_counter.py  interactive Apricorn enumeration tracker
--------------------------------------------------------------
• Counts USB2.x vs USB3.x enumerations
• Prints full WinUsbDeviceInfo dump plus bcdUSB / bcdDevice on first sighting
• Works interactively (default) or on a timer (i N)
"""
from __future__ import annotations

import argparse
import json
import logging
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Tuple

try:
    from usb_tool import find_apricorn_device   # provided library
except ImportError as exc:
    sys.stderr.write(f"fatal: usb_tool import failed  {exc}\n")
    sys.exit(1)

USB2_THRESHOLD = 3.0                     # < 3.0 → USB2
DevKey        = Tuple[str, int, int]     # (serial, bus, address)


# ────────────────────────────────── CLI / LOG ──────────────────────────────────
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Apricorn enumeration counter")
    p.add_argument("-i", "--interval", type=float, default=1.0,
                   help="seconds between scans (0 = wait for <Enter>)")
    p.add_argument("-o", "--out", type=Path, default=Path("counts.json"),
                   help="JSON stats path")
    p.add_argument("-l", "--log", type=Path, default=Path("usb_enum_counter.log"),
                   help="log file path")
    return p.parse_args()


def setup_logging(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler(path, encoding="utf-8"),
                  logging.StreamHandler(sys.stdout)],
    )


# ─────────────────────────────── core helpers ──────────────────────────────────
def safe_scan() -> list:
    try:
        return find_apricorn_device() or []
    except Exception:
        return []                         # silence  no log clutter


def atomic_write(path: Path, data: Dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(path)


# ───────────────────────────── enumeration state ───────────────────────────────
class EnumStats:
    def __init__(self) -> None:
        self.prev: Dict[DevKey, str] = {}
        self.totals = {"usb2": 0, "usb3": 0, "total": 0}

    def scan(self) -> None:
        now: Dict[DevKey, str] = {}

        for dev in safe_scan():
            key = (dev.iSerial, dev.busNumber, dev.deviceAddress)
            speed = "usb3" if dev.bcdUSB >= USB2_THRESHOLD else "usb2"
            now[key] = speed

            if key not in self.prev:
                self.totals[speed] += 1
                self.totals["total"] += 1
                logging.info(
                    "ENUM %-4s serial=%s bus=%d addr=%d bcdUSB=%s bcdDevice=%s\n%s",
                    speed.upper(), dev.iSerial, dev.busNumber, dev.deviceAddress,
                    dev.bcdUSB, dev.bcdDevice, dev
                )

        self.prev = now

    def to_json(self) -> Dict:
        return {"ts": datetime.now(timezone.utc).isoformat(), **self.totals}


# ─────────────────────────────────── main ──────────────────────────────────────
def main() -> None:
    args = parse_args()
    setup_logging(args.log)

    stats = EnumStats()
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    logging.info("enumeration tracker started")

    while True:
        stats.scan()
        atomic_write(args.out, stats.to_json())

        if args.interval <= 0:
            if input("\n<Enter> to rescan, q to quit > ").strip().lower() == "q":
                break
        else:
            time.sleep(args.interval)

    atomic_write(args.out, stats.to_json())
    logging.info("totals: %s", stats.totals)


if __name__ == "__main__":
    main()
