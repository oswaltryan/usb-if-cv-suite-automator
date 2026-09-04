# Numeric exit statuses are part of the command-line contract asserted here.
# ruff: noqa: PLR2004

import sys

import pytest

from cv_suite_automator import cli


def test_cli_runs_package_main(monkeypatch) -> None:
    calls = []
    original_argv = sys.argv
    monkeypatch.setattr(
        cli.runpy,
        "run_module",
        lambda module, run_name: calls.append((module, run_name, sys.argv.copy())),
    )

    cli.main(["run", "3861EN-FL"])

    assert calls == [("cv_suite_automator.__main__", "__main__", [original_argv[0], "3861EN-FL"])]
    assert sys.argv is original_argv


def test_cli_rejects_bare_chipset(monkeypatch, capsys) -> None:
    calls = []
    monkeypatch.setattr(cli.runpy, "run_module", lambda *args, **kwargs: calls.append(args))

    with pytest.raises(SystemExit) as exit_info:
        cli.main(["3861EN-FL"])

    assert exit_info.value.code == 2
    assert "invalid choice" in capsys.readouterr().err
    assert calls == []


@pytest.mark.parametrize("option", ["-h", "--help"])
def test_cli_help_exits_without_running_automation(monkeypatch, capsys, option: str) -> None:
    calls = []
    monkeypatch.setattr(cli.runpy, "run_module", lambda *args, **kwargs: calls.append(args))

    with pytest.raises(SystemExit) as exit_info:
        cli.main([option])

    assert exit_info.value.code == 0
    output = capsys.readouterr().out
    assert "usage: usb-if" in output
    assert "run" in output
    assert "qual" in output
    assert "parse" in output
    assert "run MSC Tests three times for storage qualification" in output
    assert "summarize failures from an existing firmware directory" in output
    assert "-h, --help" in output
    assert calls == []


def test_cli_run_help_describes_chipset(capsys) -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["run", "--help"])

    assert exit_info.value.code == 0
    output = capsys.readouterr().out
    assert "usage: usb-if run" in output
    assert "CHIPSET" in output


def test_cli_parse_help_describes_directory(capsys) -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["parse", "--help"])

    assert exit_info.value.code == 0
    output = capsys.readouterr().out
    assert "usage: usb-if parse" in output
    assert "DIRECTORY" in output


def test_cli_qual_help_describes_three_msc_attempts(capsys) -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["qual", "--help"])

    assert exit_info.value.code == 0
    output = capsys.readouterr().out
    assert "usage: usb-if qual" in output
    assert "MSC Tests three consecutive times" in output


def test_cli_runs_qualification_without_arguments(monkeypatch) -> None:
    calls = []
    original_argv = sys.argv
    monkeypatch.setattr(
        cli.runpy,
        "run_module",
        lambda module, run_name: calls.append((module, run_name, sys.argv)),
    )

    cli.main(["qual"])

    assert calls == [("cv_suite_automator.qualification", "__main__", original_argv)]


def test_cli_qual_rejects_extra_arguments(monkeypatch, capsys) -> None:
    calls = []
    monkeypatch.setattr(cli.runpy, "run_module", lambda *args, **kwargs: calls.append(args))

    with pytest.raises(SystemExit) as exit_info:
        cli.main(["qual", "chipset"])

    assert exit_info.value.code == 2
    assert "unrecognized arguments" in capsys.readouterr().err
    assert calls == []


def test_cli_parse_writes_results_without_running_automation(monkeypatch, capsys) -> None:
    calls = []
    monkeypatch.setattr(cli.runpy, "run_module", lambda *args, **kwargs: calls.append(args))
    monkeypatch.setattr(
        "cv_suite_automator.results_parser.write_results",
        lambda directory: f"{directory}\\results.json",
    )

    cli.main(["parse", r"M:\USB-IF Results\Product\v0001"])

    assert capsys.readouterr().out.strip().endswith("results.json")
    assert calls == []


def test_cli_parse_reports_validation_errors(monkeypatch, capsys) -> None:
    from cv_suite_automator.results_parser import ResultsParseError

    def fail(_directory):
        raise ResultsParseError("not a firmware directory")

    monkeypatch.setattr("cv_suite_automator.results_parser.write_results", fail)

    with pytest.raises(SystemExit) as exit_info:
        cli.main(["parse", "bad-path"])

    assert exit_info.value.code == 2
    assert "not a firmware directory" in capsys.readouterr().err
