"""Pure session-layout choices shared by hardware-backed workflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class SessionDevice(Protocol):
    """Device fields needed to construct a results session."""

    iProduct: str
    driveSizeGB: int | float


@dataclass(frozen=True)
class SessionLayout:
    """Names and locations that distinguish one session type."""

    test_description: str
    capacity_directory: str
    destination_root: str
    summary_filename: str
    uses_summary_template: bool


def standard_session_layout(
    device: SessionDevice,
    chipset: str,
    storage_manufacturer: str,
) -> SessionLayout:
    """Return the existing regression-run layout."""
    return SessionLayout(
        test_description=f"{chipset} {device.iProduct}",
        capacity_directory=f"{device.driveSizeGB}GB {storage_manufacturer}",
        destination_root=r"M:\USB-IF Results",
        summary_filename="summary.json",
        uses_summary_template=True,
    )


def qualification_session_layout(device: SessionDevice) -> SessionLayout:
    """Return the device-derived storage qualification layout."""
    return SessionLayout(
        test_description=device.iProduct,
        capacity_directory=f"{device.driveSizeGB}GB",
        destination_root=r"M:\Storage Qualification",
        summary_filename="qualification_summary.json",
        uses_summary_template=False,
    )
