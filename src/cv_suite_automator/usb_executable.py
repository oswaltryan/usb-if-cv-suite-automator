"""Apricorn device discovery through the bundled ``usb-windows.exe`` tool."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


USB_EXECUTABLE = Path(__file__).resolve().parent / "bin" / "usb-windows.exe"
USB_TOOL_TIMEOUT_SECONDS = 30


class USBExecutableError(RuntimeError):
    """Raised when the bundled USB discovery executable cannot be used."""


@dataclass(frozen=True)
class ApricornDevice:
    """Device fields emitted by ``usb-windows.exe --json`` and used here."""

    bcdUSB: float
    idVendor: str
    idProduct: str
    bcdDevice: str
    iProduct: str
    usbController: str
    driverTransport: str
    driveSizeGB: int | float

    @property
    def uses_uasp(self) -> bool:
        """Whether the device is using the UASP storage transport."""
        return self.driverTransport.upper() == "UASP"

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> ApricornDevice:
        required = (
            "bcdUSB",
            "idVendor",
            "idProduct",
            "bcdDevice",
            "iProduct",
            "usbController",
            "driverTransport",
            "driveSizeGB",
        )
        missing = [field for field in required if field not in data]
        if missing:
            raise USBExecutableError(
                "USB executable returned a device missing required fields: "
                + ", ".join(missing)
            )

        return cls(**{field: data[field] for field in required})


def _parse_usb_output(output: str) -> list[ApricornDevice]:
    """Parse JSON even when the tool writes a scan-status line first."""
    json_start = output.find("{")
    if json_start == -1:
        raise USBExecutableError("USB executable did not return a JSON object.")

    try:
        payload, _ = json.JSONDecoder().raw_decode(output[json_start:])
    except json.JSONDecodeError as exc:
        raise USBExecutableError(
            f"USB executable returned malformed JSON: {exc.msg}."
        ) from exc

    entries = payload.get("devices") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        raise USBExecutableError(
            "USB executable JSON must contain a 'devices' list."
        )

    devices: list[ApricornDevice] = []
    for entry in entries:
        if not isinstance(entry, dict) or len(entry) != 1:
            raise USBExecutableError(
                "USB executable returned an invalid numbered device entry."
            )
        device_data = next(iter(entry.values()))
        if not isinstance(device_data, dict):
            raise USBExecutableError(
                "USB executable returned invalid device details."
            )
        devices.append(ApricornDevice.from_json(device_data))

    return devices


def find_apricorn_devices(
    executable: Path = USB_EXECUTABLE,
) -> list[ApricornDevice]:
    """Run the bundled executable and return all detected Apricorn devices."""
    if not executable.is_file():
        raise USBExecutableError(
            f"USB discovery executable was not found at '{executable}'."
        )

    try:
        result = subprocess.run(
            [str(executable), "--json"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=USB_TOOL_TIMEOUT_SECONDS,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired as exc:
        raise USBExecutableError(
            f"USB discovery timed out after {USB_TOOL_TIMEOUT_SECONDS} seconds."
        ) from exc
    except OSError as exc:
        raise USBExecutableError(
            f"Unable to start USB discovery executable: {exc}."
        ) from exc

    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "no error details"
        raise USBExecutableError(
            f"USB discovery failed with exit code {result.returncode}: {detail}"
        )

    return _parse_usb_output(result.stdout)
