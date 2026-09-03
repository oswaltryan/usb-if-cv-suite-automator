from tools import quality_gate


def test_quality_gate_rejects_dirty_tree(monkeypatch, capsys) -> None:
    monkeypatch.setattr(quality_gate, "_working_tree_status", lambda: (0, "M file.py"))
    monkeypatch.setattr(quality_gate, "_run", lambda command: 0)

    assert quality_gate.run_quality_gate() == 1
    assert "requires a clean working tree" in capsys.readouterr().err


def test_quality_gate_runs_canonical_commands(monkeypatch) -> None:
    statuses = iter(((0, ""), (0, "")))
    commands = []
    monkeypatch.setattr(quality_gate, "_working_tree_status", lambda: next(statuses))
    monkeypatch.setattr(quality_gate, "_run", lambda command: commands.append(tuple(command)) or 0)

    assert quality_gate.run_quality_gate() == 0
    assert commands == [
        quality_gate.SYNC_COMMAND,
        *quality_gate.VERSION_COMMANDS,
        quality_gate.CHECK_COMMAND,
    ]


def test_quality_gate_propagates_check_failure(monkeypatch) -> None:
    statuses = iter(((0, ""), (0, "")))
    monkeypatch.setattr(quality_gate, "_working_tree_status", lambda: next(statuses))
    monkeypatch.setattr(
        quality_gate,
        "_run",
        lambda command: 5 if tuple(command) == quality_gate.CHECK_COMMAND else 0,
    )

    assert quality_gate.run_quality_gate() == 5
