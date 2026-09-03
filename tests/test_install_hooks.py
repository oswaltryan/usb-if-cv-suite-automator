import subprocess

from tools import install_hooks


def test_install_hooks_syncs_and_installs_both_hooks(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        install_hooks.subprocess,
        "run",
        lambda command, check: calls.append((command, check)),
    )

    assert install_hooks.main() == 0
    assert calls[0] == (["uv", "sync", "--locked", "--dev"], True)
    assert [call[0][-1] for call in calls[1:]] == ["pre-commit", "pre-push"]


def test_install_hooks_returns_sync_failure(monkeypatch) -> None:
    def fail(command, check):
        raise subprocess.CalledProcessError(9, command)

    monkeypatch.setattr(install_hooks.subprocess, "run", fail)

    assert install_hooks.main() == 9
