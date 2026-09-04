from types import SimpleNamespace

from cv_suite_automator.session_layout import (
    qualification_session_layout,
    standard_session_layout,
)


def test_qualification_layout_is_derived_only_from_device() -> None:
    device = SimpleNamespace(iProduct="SECURE KEY 3.0", driveSizeGB=128)

    layout = qualification_session_layout(device)

    assert layout.test_description == "SECURE KEY 3.0"
    assert layout.capacity_directory == "128GB"
    assert layout.destination_root == r"M:\Storage Qualification"
    assert layout.summary_filename == "qualification_summary.json"
    assert not layout.uses_summary_template


def test_standard_layout_remains_chipset_and_manufacturer_based() -> None:
    device = SimpleNamespace(iProduct="SECURE KEY 3.0", driveSizeGB=128)

    layout = standard_session_layout(device, "3861EN-FL", "Kioxia")

    assert layout.test_description == "3861EN-FL SECURE KEY 3.0"
    assert layout.capacity_directory == "128GB Kioxia"
    assert layout.destination_root == r"M:\USB-IF Results"
    assert layout.summary_filename == "summary.json"
    assert layout.uses_summary_template
