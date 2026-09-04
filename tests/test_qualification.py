import json
import shutil
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from cv_suite_automator import qualification
from cv_suite_automator.qualification import run_qualification
from cv_suite_automator.ui_supervisor import TestOutcome as Outcome


def _new_scratch_dir() -> Path:
    root = Path(".test-scratch")
    root.mkdir(exist_ok=True)
    scratch = root / f"qualification-{uuid.uuid4().hex}"
    scratch.mkdir(parents=True, exist_ok=False)
    return scratch


class FakeSupervisor:
    def operator_checkpoint(self, _message: str) -> None:
        raise AssertionError("No report-transfer recovery was expected")


class FakeAutomation:
    def __init__(self, summary_path: Path, outcomes) -> None:
        self.destination_drive = str(summary_path.parent)
        self.destination_reports_dir = str(summary_path.parent / "Windows 11")
        self.destination_summary_json = str(summary_path)
        self.source_reports_dir = str(summary_path.parent / "source")
        self.usb_controller_name = "Intel"
        self.usb_protocol = 3
        self.windows_version = 11
        self.current_test = None
        self.user_home = summary_path.parent
        self.ui_supervisor = FakeSupervisor()
        self.device = SimpleNamespace(
            idVendor="0984",
            idProduct="1400",
            bcdUSB=3.2,
            usbController="Intel",
        )
        self.usb_controller = 1
        self.outcomes = iter(outcomes)
        self.started = 0
        self.closed = 0
        self.run_calls = []

    def start_cv_suite(self) -> None:
        self.started += 1

    def run_test(self, test: int, *, record_outcome: bool = True) -> Outcome:
        self.run_calls.append((test, record_outcome))
        outcome = next(self.outcomes)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    def close_cv_suite(self) -> None:
        self.closed += 1


class FakeCollector:
    def __init__(self) -> None:
        self.snapshots = 0
        self.captures = []

    def snapshot(self):
        self.snapshots += 1
        return self.snapshots

    def capture_since(self, snapshot) -> None:
        self.captures.append(snapshot)


def test_qualification_runs_all_three_attempts_and_aggregates_status(monkeypatch) -> None:
    scratch = _new_scratch_dir()
    summary_path = scratch / "qualification_summary.json"
    outcomes = [
        Outcome(23, 0, "Pass"),
        Outcome(23, 2, "Fail", "Two checks failed", reconnect_required=True),
        Outcome(None, None, "Fail", "Results were unavailable"),
    ]
    automation = FakeAutomation(summary_path, outcomes)
    collector = FakeCollector()
    transfers = []
    monkeypatch.setattr(
        qualification,
        "_transfer_reports",
        lambda received_automation, received_collector: transfers.append(
            (received_automation, received_collector)
        ),
    )

    try:
        assert run_qualification(automation, collector) == 0
        written = json.loads(summary_path.read_text(encoding="utf-8"))

        assert automation.started == 1
        assert automation.closed == 1
        assert automation.run_calls == [(17, False), (17, False), (17, False)]
        assert collector.captures == [1, 2, 3]
        assert transfers == [(automation, collector)]
        assert written == {
            "test": "MSC Tests",
            "operating_system": "Windows 11",
            "controller": "Intel",
            "protocol": "USB3",
            "attempts": [
                {
                    "attempt": 1,
                    "tests_run": 23,
                    "failures": 0,
                    "status": "Pass",
                    "reason": "",
                },
                {
                    "attempt": 2,
                    "tests_run": 23,
                    "failures": 2,
                    "status": "Fail",
                    "reason": "Two checks failed",
                },
                {
                    "attempt": 3,
                    "tests_run": None,
                    "failures": None,
                    "status": "Fail",
                    "reason": "Results were unavailable",
                },
            ],
            "overall_status": "Fail",
        }
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def test_qualification_passes_only_when_all_attempts_pass(monkeypatch) -> None:
    scratch = _new_scratch_dir()
    summary_path = scratch / "qualification_summary.json"
    automation = FakeAutomation(
        summary_path,
        [Outcome(23, 0, "Pass") for _ in range(3)],
    )
    monkeypatch.setattr(qualification, "_transfer_reports", lambda *_args: None)

    try:
        assert run_qualification(automation, FakeCollector()) == 0
        written = json.loads(summary_path.read_text(encoding="utf-8"))
        assert written["overall_status"] == "Pass"
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def test_interrupted_qualification_retains_completed_attempts(monkeypatch) -> None:
    scratch = _new_scratch_dir()
    summary_path = scratch / "qualification_summary.json"
    automation = FakeAutomation(
        summary_path,
        [Outcome(23, 0, "Pass"), KeyboardInterrupt()],
    )
    collector = FakeCollector()
    monkeypatch.setattr(qualification, "_transfer_reports", lambda *_args: None)

    try:
        with pytest.raises(KeyboardInterrupt):
            run_qualification(automation, collector)

        written = json.loads(summary_path.read_text(encoding="utf-8"))
        assert len(written["attempts"]) == 1
        assert written["attempts"][0]["attempt"] == 1
        assert written["overall_status"] == "In Progress"
        assert collector.captures == [1, 2]
        assert automation.closed == 1
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def test_qualification_waits_for_same_dut_on_usb3_before_starting(monkeypatch) -> None:
    scratch = _new_scratch_dir()
    summary_path = scratch / "qualification_summary.json"
    automation = FakeAutomation(
        summary_path,
        [Outcome(23, 0, "Pass") for _ in range(3)],
    )
    automation.usb_protocol = 2
    automation.device.bcdUSB = 2.1
    usb2_device = SimpleNamespace(
        idVendor="0984",
        idProduct="1400",
        bcdUSB=2.1,
        usbController="Intel",
    )
    wrong_usb3_device = SimpleNamespace(
        idVendor="0984",
        idProduct="9999",
        bcdUSB=3.2,
        usbController="Intel",
    )
    matching_usb3_device = SimpleNamespace(
        idVendor="0984",
        idProduct="1400",
        bcdUSB=3.2,
        usbController="ASMedia",
    )
    discoveries = iter(([usb2_device], [wrong_usb3_device], [matching_usb3_device]))
    sleeps = []
    monkeypatch.setattr(qualification, "_transfer_reports", lambda *_args: None)

    try:
        result = run_qualification(
            automation,
            FakeCollector(),
            device_finder=lambda: next(discoveries),
            sleeper=sleeps.append,
        )

        assert result == 0
        assert sleeps == [5, 5]
        assert automation.started == 1
        assert automation.closed == 1
        assert automation.device is matching_usb3_device
        assert automation.usb_protocol == qualification.USB3_PROTOCOL
        assert automation.usb_controller_name == "ASMedia"
        assert automation.usb_controller == 0
        written = json.loads(summary_path.read_text(encoding="utf-8"))
        assert written["controller"] == "ASMedia"
        assert written["protocol"] == "USB3"
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
