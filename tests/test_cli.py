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

    cli.main(["3861EN-FL"])

    assert calls == [("cv_suite_automator.__main__", "__main__", [original_argv[0], "3861EN-FL"])]
    assert sys.argv is original_argv


@pytest.mark.parametrize("option", ["-h", "--help"])
def test_cli_help_exits_without_running_automation(monkeypatch, capsys, option: str) -> None:
    calls = []
    monkeypatch.setattr(cli.runpy, "run_module", lambda *args, **kwargs: calls.append(args))

    with pytest.raises(SystemExit) as exit_info:
        cli.main([option])

    assert exit_info.value.code == 0
    output = capsys.readouterr().out
    assert "usage: usb-if" in output
    assert "CHIPSET" in output
    assert "-h, --help" in output
    assert calls == []
