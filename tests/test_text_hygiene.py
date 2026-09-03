from tools.text_hygiene import check_file


def test_text_hygiene_accepts_clean_lf_file(tmp_path) -> None:
    path = tmp_path / "clean.txt"
    path.write_bytes(b"clean\n")

    assert check_file(path) == []


def test_text_hygiene_reports_crlf_trailing_space_and_missing_newline(tmp_path) -> None:
    path = tmp_path / "bad.txt"
    path.write_bytes(b"bad \r\nlast")

    failures = check_file(path)

    assert any("CRLF" in failure for failure in failures)
    assert any("trailing whitespace" in failure for failure in failures)
    assert any("missing final newline" in failure for failure in failures)
