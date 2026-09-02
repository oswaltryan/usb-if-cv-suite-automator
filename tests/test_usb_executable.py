import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from cv_suite_automator import usb_executable
from cv_suite_automator.usb_executable import USBExecutableError


DEVICE_OUTPUT = """Scanning for Apricorn devices...
{
  "devices": [
    {
      "1": {
        "bcdUSB": 3.2,
        "idVendor": "0984",
        "idProduct": "1410",
        "bcdDevice": "0705",
        "iProduct": "SECURE KEY 3.0",
        "usbController": "ASMedia",
        "driverTransport": "BOT",
        "driveSizeGB": 4
      }
    }
  ]
}
"""


def test_parse_usb_output_maps_device_fields() -> None:
    devices = usb_executable._parse_usb_output(DEVICE_OUTPUT)

    assert len(devices) == 1
    assert devices[0].iProduct == "SECURE KEY 3.0"
    assert devices[0].bcdUSB == 3.2
    assert devices[0].driverTransport == "BOT"
    assert devices[0].driveSizeGB == 4


def test_parse_usb_output_handles_no_devices() -> None:
    assert usb_executable._parse_usb_output(
        'Scanning for Apricorn devices...\n{"devices": []}'
    ) == []


@pytest.mark.parametrize(
    "transport, expected",
    [("UASP", True), ("uasp", True), ("BOT", False)],
)
def test_device_identifies_uasp_transport(transport: str, expected: bool) -> None:
    output = DEVICE_OUTPUT.replace('"BOT"', f'"{transport}"')

    assert usb_executable._parse_usb_output(output)[0].uses_uasp is expected


@pytest.mark.parametrize(
    "output, message",
    [
        ("not json", "did not return a JSON object"),
        ('{"devices":', "malformed JSON"),
        ('{"wrong": []}', "'devices' list"),
        ('{"devices": [{"1": {}}]}', "missing required fields"),
    ],
)
def test_parse_usb_output_rejects_invalid_data(output: str, message: str) -> None:
    with pytest.raises(USBExecutableError, match=message):
        usb_executable._parse_usb_output(output)


def test_find_apricorn_devices_runs_bundled_command(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    executable = tmp_path / "usb-windows.exe"
    executable.touch()
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout=DEVICE_OUTPUT, stderr="")

    monkeypatch.setattr(usb_executable.subprocess, "run", fake_run)

    devices = usb_executable.find_apricorn_devices(executable)

    assert devices[0].idVendor == "0984"
    assert calls[0][0] == [str(executable), "--json"]
    assert calls[0][1]["timeout"] == usb_executable.USB_TOOL_TIMEOUT_SECONDS


def test_find_apricorn_devices_reports_missing_executable(tmp_path: Path) -> None:
    with pytest.raises(USBExecutableError, match="was not found"):
        usb_executable.find_apricorn_devices(tmp_path / "missing.exe")


def test_find_apricorn_devices_reports_nonzero_exit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    executable = tmp_path / "usb-windows.exe"
    executable.touch()
    monkeypatch.setattr(
        usb_executable.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=2, stdout="", stderr="scan failed"
        ),
    )

    with pytest.raises(USBExecutableError, match="exit code 2: scan failed"):
        usb_executable.find_apricorn_devices(executable)


def test_find_apricorn_devices_reports_timeout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    executable = tmp_path / "usb-windows.exe"
    executable.touch()

    def time_out(*args, **kwargs):
        raise subprocess.TimeoutExpired("usb-windows.exe", 30)

    monkeypatch.setattr(usb_executable.subprocess, "run", time_out)

    with pytest.raises(USBExecutableError, match="timed out"):
        usb_executable.find_apricorn_devices(executable)
