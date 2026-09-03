from pathlib import Path

import pytest

from cv_suite_automator.ui_supervisor import (
    CVSuiteUISupervisor,
    DialogRule,
    EventKind,
    WindowSnapshot,
    classify_windows,
    device_item_matches,
    latest_failed_test_name,
    parse_log_results,
)


def window(
    title: str, *texts: str, buttons=(), has_list_box=False, visible=True
):
    return WindowSnapshot(
        handle=hash((title, texts)), title=title, texts=texts,
        buttons=buttons, has_list_box=has_list_box, visible=visible,
    )


def test_failure_preempts_expected_prompt_and_results() -> None:
    snapshots = [
        window("Results", buttons=("OK",)),
        window("USB Command Verifier (xHCI - USB 3)", "Expected prompt"),
        window("Error", "No Device Under Test", buttons=("OK",)),
    ]
    event = classify_windows(
        snapshots, [DialogRule(1, "Expected prompt")], set(),
        ["No Device Under Test"], True,
    )
    assert event.kind is EventKind.FAILURE


def test_historical_failure_text_in_main_log_does_not_retrigger() -> None:
    event = classify_windows(
        [window("USB 3 Gen X Command Verifier", "old: No Device Under Test")],
        [], set(), ["No Device Under Test"], True,
    )
    assert event.kind is EventKind.IDLE


def test_generic_failure_wording_in_main_log_does_not_retrigger() -> None:
    event = classify_windows(
        [window("USB 3 Gen X Command Verifier", "old test has failed")],
        [], set(), [], True,
    )
    assert event.kind is EventKind.IDLE


@pytest.mark.parametrize(
    "popup",
    [
        window("Test Failure Details", "Unexpected condition"),
        window("USB Command Verifier (xHCI - USB 3)", "The test has failed"),
    ],
)
def test_generic_failure_popup_is_recognized(popup: WindowSnapshot) -> None:
    event = classify_windows([popup], [], set(), [], True)
    assert event.kind is EventKind.FAILURE


def test_prompts_can_arrive_out_of_declared_order() -> None:
    rules = [DialogRule(1, "First"), DialogRule(2, "Second", "Yes")]
    event = classify_windows(
        [window("USB Command Verifier (xHCI - USB 3)", "Second")],
        rules, set(), [], True,
    )
    assert event.kind is EventKind.PROMPT
    assert event.rule == rules[1]


def test_handled_prompt_is_not_clicked_twice() -> None:
    event = classify_windows(
        [window("USB Command Verifier (xHCI - USB 3)", "Prompt")],
        [DialogRule(1, "Prompt")], {1}, [], True,
    )
    assert event.kind is EventKind.IDLE


def test_device_selector_is_recognized_before_unknown_window() -> None:
    event = classify_windows(
        [window("USB Command Verifier (xHCI - USB 3)", "Select device", has_list_box=True)],
        [], set(), [], False,
    )
    assert event.kind is EventKind.DEVICE_SELECTION


def test_unknown_popup_is_never_treated_as_a_prompt() -> None:
    event = classify_windows(
        [window("Unexpected warning", "Something changed", buttons=("OK",))],
        [], set(), [], True,
    )
    assert event.kind is EventKind.UNKNOWN


def test_hidden_ime_helper_window_is_ignored() -> None:
    event = classify_windows(
        [window("M", visible=False), window("Default IME", visible=False)],
        [], set(), [], True,
    )
    assert event.kind is EventKind.IDLE


def test_running_title_is_still_recognized_as_main_window() -> None:
    event = classify_windows(
        [window("USB 3 Gen X Command Verifier - Running: TD 9.6", "log")],
        [], set(), [], True,
    )
    assert event.kind is EventKind.IDLE


def test_error_recovery_test_title_is_not_a_failure_popup() -> None:
    event = classify_windows(
        [
            window(
                "USB 3 Gen X Command Verifier - Running: Error Recovery Test",
                "Now Starting Test: USB Mass Storage Error Recovery Test",
            )
        ],
        [DialogRule(2, "Disconnect and power off MSC device")],
        set(), [], True,
    )
    assert event.kind is EventKind.IDLE


def test_msc_disconnect_prompt_is_auto_acknowledged() -> None:
    prompt_text = (
        "Disconnect and power off MSC device, then click OK.  "
        "To abort this test, click ABORT"
    )
    rule = DialogRule(2, prompt_text, "OK")
    event = classify_windows(
        [
            window(
                "USB Command Verifier (xHCI - USB 3)",
                prompt_text,
                buttons=("OK", "ABORT"),
            )
        ],
        [rule], set(), [], True,
    )
    assert event.kind is EventKind.PROMPT
    assert event.rule.button == "OK"


@pytest.mark.parametrize(
    "line, expected",
    [
        ("Tests run (20), Failures (0)", (20, 0, "Pass")),
        ("Tests run (7) other text Failures (2)", (7, 2, "Fail")),
        ("    [ Passed (53); Failed (0) ]", (53, 0, "Pass")),
        ("TEST RESULTS: [ Passed (51); Failed (2) ]", (53, 2, "Fail")),
    ],
)
def test_parse_log_results(line: str, expected: tuple[int, int, str]) -> None:
    outcome = parse_log_results(["old line", line])
    assert outcome is not None
    assert (outcome.tests_run, outcome.failures, outcome.status) == expected


def test_parse_log_results_uses_latest_complete_result() -> None:
    outcome = parse_log_results([
        "Tests run (2), Failures (1)", "progress", "Tests run (3), Failures (0)"
    ])
    assert outcome is not None
    assert outcome.summary_values() == [3, 0, "Pass"]


def test_parse_log_results_rejects_missing_counts() -> None:
    assert parse_log_results(["Test complete", "Failures unavailable"]) is None


def test_latest_failed_test_name_uses_last_failing_subtest() -> None:
    name = latest_failed_test_name(
        [
            "Stopping Test [ First Test:\n    Number of: Fails (1); Aborts (0) ]",
            "Stopping Test [ Passing Test:\n    Number of: Fails (0); Aborts (0) ]",
            "Stopping Test [ Relevant Failure:\n    Number of: Fails (2); Aborts (0) ]",
        ]
    )

    assert name == "Relevant Failure"


def test_latest_failed_test_name_returns_none_without_failed_subtest() -> None:
    assert latest_failed_test_name(
        ["Stopping Test [ Passing Test:\n Number of: Fails (0); Aborts (0) ]"]
    ) is None


def test_failed_tree_item_is_scrolled_into_view_for_diagnostics(tmp_path: Path) -> None:
    class Log:
        def texts(self):
            return []

    class Item:
        def __init__(self):
            self.was_revealed = False

        def text(self):
            return "TD 9.15 L1 Suspend/Resume Test (Configuration Index 0)"

        def sub_elements(self):
            return []

        def ensure_visible(self):
            self.was_revealed = True

    item = Item()

    class Tree:
        def friendly_class_name(self):
            return "TreeView"

        def class_name(self):
            return "SysTreeView32"

        def window_text(self):
            return ""

        def roots(self):
            return [item]

    class Main:
        def descendants(self):
            tree = Tree()

            class LogText:
                def friendly_class_name(self):
                    return "Edit"

                def class_name(self):
                    return "RichEdit"

                def window_text(self):
                    return (
                        "Stopping Test [ L1Suspend/Resume Test "
                        "(Configuration Index 0):\n"
                        " Number of: Fails (1); Aborts (0) ]"
                    )

            return [tree, LogText()]

    supervisor = CVSuiteUISupervisor(
        EmptyApp(), None, Log(), tmp_path, [], operator_input=lambda _: ""
    )

    assert supervisor._reveal_failed_test(Main()) is True
    assert item.was_revealed is True


class EmptyApp:
    def windows(self):
        return []


class EmptyLog:
    def texts(self):
        return []


class FocusableWindow:
    def __init__(self, minimized=False):
        self.minimized = minimized
        self.restored = False
        self.focused = False

    def is_minimized(self):
        return self.minimized

    def restore(self):
        self.restored = True

    def set_focus(self):
        self.focused = True

    def exists(self, timeout=None):
        return True

    def is_visible(self):
        return True

    def is_enabled(self):
        return True

    def child_window(self, **kwargs):
        return EmptyLog()


class MainWindowApp(EmptyApp):
    def __init__(self, main_window):
        self.main_window = main_window

    def window(self, **kwargs):
        return self.main_window


class SequenceSupervisor(CVSuiteUISupervisor):
    def __init__(self, tmp_path: Path, sequences, log_lines):
        super().__init__(
            EmptyApp(), None, EmptyLog(), tmp_path, ["No Device Under Test"],
            operator_input=lambda _: "", poll_interval=0,
        )
        self.sequences = list(sequences)
        self.last_sequence = []
        self.log_lines = log_lines
        self.clicked = []

    def snapshots(self):
        if self.sequences:
            self.last_sequence = self.sequences.pop(0)
        return self.last_sequence

    def _log_lines(self):
        return list(self.log_lines)

    def click_button(self, window, button, phase):
        self.clicked.append((window.title, button, phase))

    def select_device(self, window, vendor_id, product_id):
        return True

    def wait_for_main_window(self, phase):
        return None

    def prepare_for_test_retry(self, context):
        return None


def test_diagnostics_are_written_when_screenshot_is_unavailable(tmp_path: Path) -> None:
    supervisor = CVSuiteUISupervisor(
        EmptyApp(), None, EmptyLog(), tmp_path, [], operator_input=lambda _: ""
    )
    incident = supervisor.capture_diagnostics(
        "unknown popup", [window("Unexpected", "details")], {"test": 6}
    )
    content = (incident / "incident.json").read_text(encoding="utf-8")
    assert "unknown popup" in content
    assert "Unexpected" in content
    assert '"test": 6' in content


def test_diagnostics_do_not_capture_hidden_helper_windows(tmp_path: Path) -> None:
    class SavedImage:
        def save(self, path):
            Path(path).write_bytes(b"image")

    class CapturableWindow:
        def __init__(self):
            self.capture_count = 0

        def capture_as_image(self):
            self.capture_count += 1
            return SavedImage()

    visible_wrapper = CapturableWindow()
    hidden_wrapper = CapturableWindow()
    visible = window("USB 3 Gen X Command Verifier", visible=True)
    visible.wrapper = visible_wrapper
    hidden = window("", visible=False)
    hidden.wrapper = hidden_wrapper
    supervisor = CVSuiteUISupervisor(
        EmptyApp(), None, EmptyLog(), tmp_path, [], operator_input=lambda _: ""
    )

    incident = supervisor.capture_diagnostics("failure", [visible, hidden])

    assert visible_wrapper.capture_count == 1
    assert hidden_wrapper.capture_count == 0
    assert (incident / "window-1.png").exists()
    assert not (incident / "window-2.png").exists()


def test_safe_action_is_retried_before_operator_escalation(tmp_path: Path) -> None:
    supervisor = CVSuiteUISupervisor(
        EmptyApp(), None, EmptyLog(), tmp_path, [],
        operator_input=lambda _: "", poll_interval=0,
    )
    attempts = 0

    def eventually_succeeds():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RuntimeError("stale control")
        return "done"

    assert supervisor.perform_action(eventually_succeeds, "test action") == "done"
    assert attempts == 3
    assert list(tmp_path.iterdir()) == []


def test_focus_main_window_restores_and_activates_cv_suite(tmp_path: Path) -> None:
    main_window = FocusableWindow(minimized=True)
    supervisor = CVSuiteUISupervisor(
        EmptyApp(), main_window, EmptyLog(), tmp_path, []
    )

    supervisor.focus_main_window()

    assert main_window.restored is True
    assert main_window.focused is True


def test_modal_transition_waits_for_and_focuses_main_window(tmp_path: Path) -> None:
    main_window = FocusableWindow()
    supervisor = CVSuiteUISupervisor(
        MainWindowApp(main_window), None, EmptyLog(), tmp_path, [], poll_interval=0
    )

    supervisor.wait_for_main_window("controller confirmation")

    assert supervisor.main_window is main_window
    assert main_window.focused is True


def test_monitor_drives_device_prompt_and_result_sequence(tmp_path: Path) -> None:
    device = window(
        "USB Command Verifier (xHCI - USB 3)", "Select device",
        has_list_box=True,
    )
    prompt = window(
        "USB Command Verifier (xHCI - USB 3)", "Second", buttons=("Yes",)
    )
    results = window("Results", buttons=("OK",))
    supervisor = SequenceSupervisor(
        tmp_path, [[device], [prompt], [results]],
        ["Tests run (4), Failures (0)"],
    )

    outcome = supervisor.monitor_test(
        [DialogRule(1, "First"), DialogRule(2, "Second", "Yes")],
        "0984", "1410", {"test": 3}, baseline_log=("old",),
    )

    assert outcome.summary_values() == [4, 0, "Pass"]
    assert (prompt.title, "Yes", "test prompt") in supervisor.clicked
    assert (results.title, "OK", "results acknowledgement") in supervisor.clicked


def test_monitor_failure_preempts_and_returns_null_count_failure(tmp_path: Path) -> None:
    device = window(
        "USB Command Verifier (xHCI - USB 3)", "Select device",
        has_list_box=True,
    )
    failure = window("Failure Details", "The test failed", buttons=("OK",))
    supervisor = SequenceSupervisor(tmp_path, [[device], [failure]], [])

    outcome = supervisor.monitor_test([], "0984", "1410", {"test": 6})

    assert outcome.summary_values() == [None, None, "Fail"]
    assert supervisor.clicked == [
        (failure.title, "OK", "failure acknowledgement")
    ]
    assert list(tmp_path.glob("*/incident.json"))


@pytest.mark.parametrize(
    "item",
    [
        "VID=0984, PID=1410",
        "USB\\VID_0984&PID_1410",
        "VID: 0984 PID: 1410 Apricorn",
    ],
)
def test_device_item_requires_exact_vid_and_pid(item: str) -> None:
    assert device_item_matches(item, "0984", "1410")
    assert not device_item_matches(item, "0984", "1411")


def test_results_before_device_selection_can_never_report_pass(tmp_path: Path) -> None:
    results = window("Results", buttons=("OK",))
    supervisor = SequenceSupervisor(
        tmp_path, [[results]], ["Tests run (4), Failures (0)"]
    )

    outcome = supervisor.monitor_test(
        [], "0984", "1410", {"test": 3}, baseline_log=("old",)
    )

    assert outcome.retry_required
    assert outcome.tests_run is None
    assert outcome.failures is None
    assert (results.title, "OK", "invalid device-selection attempt") in supervisor.clicked
