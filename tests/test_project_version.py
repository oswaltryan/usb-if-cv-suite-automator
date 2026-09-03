from tools import project_version


def test_project_and_lock_versions_match() -> None:
    assert project_version.versions() == ("0.2.1", "0.2.1")


def test_version_check_reports_mismatch(monkeypatch, capsys) -> None:
    monkeypatch.setattr(project_version, "versions", lambda: ("1.0.0", "1.0.1"))

    assert project_version.main(["check"]) == 1
    assert "Version mismatch" in capsys.readouterr().err
