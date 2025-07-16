#!/usr/bin/env python3
"""
usb_enum_counter.py – Apricorn enumeration tracker (macOS compatible)
----------------------------------------------------------------------
• Tracks USB enumerations (USB2 vs USB3) using serial and location_id
• Counts even if enumerated again on same port
• Interactive or interval-based
"""

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
    sys.stderr.write(f"fatal: usb_tool import failed – {exc}\n")
    sys.exit(1)

USB2_THRESHOLD = 3.0
DEVICE_TIMEOUT = 2.5  # seconds after disappearance to reset

DeviceKey = Tuple[str, str]  # (serial_num, location_id)


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


def safe_scan() -> list:
    try:
        return find_apricorn_device() or []
    except Exception:
        return []


def atomic_write(path: Path, data: Dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(path)


class EnumStats:
    def __init__(self) -> None:
        self.totals = {"usb2": 0, "usb3": 0, "total": 0}
        self.last_seen: Dict[DeviceKey, float] = {}

    def scan(self) -> None:
        current_time = time.time()
        active_devices: Dict[DeviceKey, float] = {}

        for dev in safe_scan():
            serial = getattr(dev, "serial_num", None) or getattr(dev, "iSerial", "unknown")
            location = getattr(dev, "location_id", "unknown").split()[0]
            key = (serial, location)
            bcdUSB = float(getattr(dev, "bcdUSB", 0.0))
            speed = "usb3" if bcdUSB >= USB2_THRESHOLD else "usb2"

            was_recent = key in self.last_seen and (current_time - self.last_seen[key]) < DEVICE_TIMEOUT

            # If not seen recently, count as new enumeration
            if not was_recent:
                self.totals[speed] += 1
                self.totals["total"] += 1
                logging.info(
                    "ENUM %-4s serial=%s location=%s bcdUSB=%s",
                    speed.upper(), serial, location, bcdUSB
                )

            active_devices[key] = current_time

        # Update last seen only for active devices
        self.last_seen.update(active_devices)

    def to_json(self) -> Dict:
        return {
            "ts": datetime.now(timezone.utc).isoformat(),
            "totals": self.totals,
        }


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
