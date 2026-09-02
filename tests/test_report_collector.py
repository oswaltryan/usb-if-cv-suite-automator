import shutil
import uuid
from pathlib import Path

import pytest

from cv_suite_automator.report_collector import ReportCollector, ReportTransferError


def _scratch() -> Path:
    path = Path(".test-scratch") / f"reports-{uuid.uuid4().hex}"
    path.mkdir(parents=True)
    return path


def test_only_new_automation_reports_are_moved() -> None:
    scratch = _scratch()
    source = scratch / "source"
    manual = source / "manual-run"
    manual.mkdir(parents=True)
    manual_report = manual / "manual.html"
    manual_report.write_text("manual", encoding="utf-8")
    collector = ReportCollector(source)
    before = collector.snapshot()

    automated = source / "automated-run"
    automated.mkdir()
    automated_report = automated / "report.html"
    automated_report.write_text("automated", encoding="utf-8")
    note = automated / "notes.txt"
    note.write_text("keep me", encoding="utf-8")
    collector.capture_since(before)

    destination = scratch / "backup"
    archive = source / "device" / "session" / "Windows 11" / "Intel" / "USB3"
    try:
        collector.transfer(destination, archive)
        assert manual_report.read_text(encoding="utf-8") == "manual"
        assert (destination / "report.html").read_text(encoding="utf-8") == "automated"
        assert (archive / "report.html").read_text(encoding="utf-8") == "automated"
        assert not automated_report.exists()
        assert note.read_text(encoding="utf-8") == "keep me"
        assert automated.is_dir()
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def test_modified_preexisting_report_is_not_claimed() -> None:
    scratch = _scratch()
    source = scratch / "source"
    source.mkdir()
    report = source / "manual.html"
    report.write_text("before", encoding="utf-8")
    collector = ReportCollector(source)
    before = collector.snapshot()
    report.write_text("after", encoding="utf-8")

    try:
        assert collector.capture_since(before) == set()
        collector.transfer(scratch / "backup", source / "archive")
        assert report.read_text(encoding="utf-8") == "after"
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def test_collision_suffix_and_empty_owned_directory_cleanup() -> None:
    scratch = _scratch()
    source = scratch / "source"
    source.mkdir()
    collector = ReportCollector(source)
    before = collector.snapshot()
    generated = source / "generated"
    generated.mkdir()
    (generated / "report.html").write_text("new", encoding="utf-8")
    collector.capture_since(before)
    destination = scratch / "backup"
    destination.mkdir()
    (destination / "report.html").write_text("old", encoding="utf-8")
    archive = source / "archive"

    try:
        collector.transfer(destination, archive)
        assert (destination / "report.html").read_text(encoding="utf-8") == "old"
        assert (destination / "report_1.html").read_text(encoding="utf-8") == "new"
        assert (archive / "report_1.html").read_text(encoding="utf-8") == "new"
        assert not generated.exists()
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def test_verification_failure_preserves_source(monkeypatch) -> None:
    scratch = _scratch()
    source = scratch / "source"
    source.mkdir()
    collector = ReportCollector(source)
    before = collector.snapshot()
    report = source / "report.html"
    report.write_text("source content", encoding="utf-8")
    collector.capture_since(before)

    def corrupt_copy(_source, destination):
        Path(destination).write_text("corrupt", encoding="utf-8")

    monkeypatch.setattr("cv_suite_automator.report_collector.shutil.copy2", corrupt_copy)
    try:
        with pytest.raises(ReportTransferError, match="Verification failed"):
            collector.transfer(scratch / "backup", source / "archive")
        assert report.read_text(encoding="utf-8") == "source content"
        assert not list((scratch / "backup").iterdir())
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def test_unavailable_destination_uses_existing_fallback_behavior() -> None:
    scratch = _scratch()
    source = scratch / "source"
    source.mkdir()
    collector = ReportCollector(source)
    before = collector.snapshot()
    (source / "report.html").write_text("report", encoding="utf-8")
    collector.capture_since(before)
    blocked_destination = scratch / "not-a-directory"
    blocked_destination.write_text("blocked", encoding="utf-8")
    fallback = scratch / "fallback"

    try:
        collector.transfer(blocked_destination, source / "archive", fallback)
        assert (fallback / "report.html").read_text(encoding="utf-8") == "report"
        assert (source / "archive" / "report.html").read_text(encoding="utf-8") == "report"
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
