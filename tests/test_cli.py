from cv_suite_automator import cli


def test_cli_runs_package_main(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        cli.runpy,
        "run_module",
        lambda module, run_name: calls.append((module, run_name)),
    )

    cli.main()

    assert calls == [("cv_suite_automator.__main__", "__main__")]
