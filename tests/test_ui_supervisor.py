from pathlib import Path

import pytest

from cv_suite_automator.ui_supervisor import (
    CVSuiteUISupervisor,
    DialogRule,
    EventKind,
    WindowSnapshot,
    classify_windows,
    device_item_matches,
    parse_log_results,
)


def window(title: str, *texts: str, buttons=(), has_list_box=False, visible=True):
    return WindowSnapshot(
        handle=hash((title, texts)),
        title=title,
        texts=texts,
        buttons=buttons,
        has_list_box=has_list_box,
        visible=visible,
    )


def test_failure_preempts_expected_prompt_and_results() -> None:
    snapshots = [
        window("Results", buttons=("OK",)),
        window("USB Command Verifier (xHCI - USB 3)", "Expected prompt"),
        window("Error", "No Device Under Test", buttons=("OK",)),
    ]
    event = classify_windows(
        snapshots,
        [DialogRule(1, "Expected prompt")],
        set(),
        ["No Device Under Test"],
        True,
    )
    assert event.kind is EventKind.FAILURE


def test_historical_failure_text_in_main_log_does_not_retrigger() -> None:
    event = classify_windows(
        [window("USB 3 Gen X Command Verifier", "old: No Device Under Test")],
        [],
        set(),
        ["No Device Under Test"],
        True,
    )
    assert event.kind is EventKind.IDLE


def test_generic_failure_wording_in_main_log_does_not_retrigger() -> None:
    event = classify_windows(
        [window("USB 3 Gen X Command Verifier", "old test has failed")],
        [],
        set(),
        [],
        True,
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
        rules,
        set(),
        [],
        True,
    )
    assert event.kind is EventKind.PROMPT
    assert event.rule == rules[1]


def test_handled_prompt_is_not_clicked_twice() -> None:
    event = classify_windows(
        [window("USB Command Verifier (xHCI - USB 3)", "Prompt")],
        [DialogRule(1, "Prompt")],
        {1},
        [],
        True,
    )
    assert event.kind is EventKind.IDLE


def test_device_selector_is_recognized_before_unknown_window() -> None:
    event = classify_windows(
        [window("USB Command Verifier (xHCI - USB 3)", "Select device", has_list_box=True)],
        [],
        set(),
        [],
        False,
    )
    assert event.kind is EventKind.DEVICE_SELECTION


def test_unknown_popup_is_never_treated_as_a_prompt() -> None:
    event = classify_windows(
        [window("Unexpected warning", "Something changed", buttons=("OK",))],
        [],
        set(),
        [],
        True,
    )
    assert event.kind is EventKind.UNKNOWN


def test_hidden_ime_helper_window_is_ignored() -> None:
    event = classify_windows(
        [window("M", visible=False), window("Default IME", visible=False)],
        [],
        set(),
        [],
        True,
    )
    assert event.kind is EventKind.IDLE


def test_running_title_is_still_recognized_as_main_window() -> None:
    event = classify_windows(
        [window("USB 3 Gen X Command Verifier - Running: TD 9.6", "log")],
        [],
        set(),
        [],
        True,
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
        set(),
        [],
        True,
    )
    assert event.kind is EventKind.IDLE


def test_msc_disconnect_prompt_is_auto_acknowledged() -> None:
    prompt_text = (
        "Disconnect and power off MSC device, then click OK.  To abort this test, click ABORT"
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
        [rule],
        set(),
        [],
        True,
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
    outcome = parse_log_results(
        ["Tests run (2), Failures (1)", "progress", "Tests run (3), Failures (0)"]
    )
    assert outcome is not None
    assert outcome.summary_values() == [3, 0, "Pass"]


def test_parse_log_results_rejects_missing_counts() -> None:
    assert parse_log_results(["Test complete", "Failures unavailable"]) is None


def test_known_device_failure_requires_reconnect() -> None:
    event = classify_windows(
        [window("Error", "No Device Under Test")],
        [],
        set(),
        ["No Device Under Test"],
        True,
    )

    assert event.kind is EventKind.FAILURE
    assert event.reconnect_required


def test_generic_compliance_failure_does_not_require_reconnect() -> None:
    event = classify_windows(
        [window("Test Failure Details", "A compliance assertion failed")],
        [],
        set(),
        ["No Device Under Test"],
        True,
    )

    assert event.kind is EventKind.FAILURE
    assert not event.reconnect_required


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


class StaticControl:
    def __init__(self, *, selected=(), item_count=0, enabled=False):
        self.selected = selected
        self.count = item_count
        self.enabled = enabled

    def wrapper_object(self):
        return self

    def selected_indices(self):
        return self.selected

    def item_count(self):
        return self.count

    def is_enabled(self):
        return self.enabled


class LaunchMainWindow:
    def __init__(self, test_index: int):
        self.controls = {
            1001: StaticControl(selected=(test_index,)),
            1002: StaticControl(item_count=1),
            1013: StaticControl(enabled=True),
        }

    def child_window(self, control_id):
        return self.controls[control_id]


class ReadinessSupervisor(CVSuiteUISupervisor):
    def __init__(self, test_index: int, log_sequences):
        super().__init__(
            EmptyApp(),
            LaunchMainWindow(test_index),
            EmptyLog(),
            [],
            poll_interval=0,
        )
        self.log_sequences = list(log_sequences)
        self.last_log = []
        self.log_reads = 0

    def _log_lines(self):
        self.log_reads += 1
        if self.log_sequences:
            self.last_log = self.log_sequences.pop(0)
        return list(self.last_log)


def test_suite_readiness_requires_new_validation_and_two_stable_polls() -> None:
    baseline = ("Old suite", "Validation succeeded!")
    supervisor = ReadinessSupervisor(
        17,
        [
            list(baseline),
            [*baseline, 'Validating "MSC Tests.cvtests" with MSXML Version 6...'],
            [*baseline, "Validating MSC", "Validation succeeded!"],
            [*baseline, "Validating MSC", "Validation succeeded!"],
        ],
    )

    launch_baseline = supervisor.wait_for_suite_ready(17, baseline, validation_required=True)

    assert launch_baseline[-1] == "Validation succeeded!"
    assert supervisor.log_reads == 4


def test_already_selected_suite_can_use_its_existing_ready_state() -> None:
    supervisor = ReadinessSupervisor(17, [["existing log"], ["existing log"]])

    launch_baseline = supervisor.wait_for_suite_ready(
        17, ("existing log",), validation_required=False
    )

    assert launch_baseline == ("existing log",)
    assert supervisor.log_reads == 2


def test_launch_confirmation_ignores_historical_start_log_and_waits_for_transition() -> None:
    class LaunchSupervisor(ReadinessSupervisor):
        def __init__(self):
            super().__init__(17, [["Now Starting Test: old"], ["Now Starting Test: old"]])
            self.window_sequences = [
                [window("USB 3 Gen X Command Verifier")],
                [
                    window("USB 3 Gen X Command Verifier"),
                    window("USB Command Verifier (xHCI - USB 3)", "Select device"),
                ],
            ]
            self.snapshot_reads = 0

        def snapshots(self):
            self.snapshot_reads += 1
            return self.window_sequences.pop(0)

    supervisor = LaunchSupervisor()

    supervisor.wait_for_test_launch(("Now Starting Test: old",))

    assert supervisor.snapshot_reads == 2


class SequenceSupervisor(CVSuiteUISupervisor):
    def __init__(self, _tmp_path: Path, sequences, log_lines):
        super().__init__(
            EmptyApp(),
            None,
            EmptyLog(),
            ["No Device Under Test"],
            operator_input=lambda _: "",
            poll_interval=0,
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

    def prepare_for_test_retry(self):
        return None


def test_safe_action_is_retried_before_operator_escalation(tmp_path: Path) -> None:
    supervisor = CVSuiteUISupervisor(
        EmptyApp(),
        None,
        EmptyLog(),
        [],
        operator_input=lambda _: "",
        poll_interval=0,
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


def test_focus_main_window_restores_and_activates_cv_suite() -> None:
    main_window = FocusableWindow(minimized=True)
    supervisor = CVSuiteUISupervisor(EmptyApp(), main_window, EmptyLog(), [])

    supervisor.focus_main_window()

    assert main_window.restored is True
    assert main_window.focused is True


def test_modal_transition_waits_for_and_focuses_main_window() -> None:
    main_window = FocusableWindow()
    supervisor = CVSuiteUISupervisor(
        MainWindowApp(main_window), None, EmptyLog(), [], poll_interval=0
    )

    supervisor.wait_for_main_window("controller confirmation")

    assert supervisor.main_window is main_window
    assert main_window.focused is True


def test_monitor_drives_device_prompt_and_result_sequence(tmp_path: Path) -> None:
    device = window(
        "USB Command Verifier (xHCI - USB 3)",
        "Select device",
        has_list_box=True,
    )
    prompt = window("USB Command Verifier (xHCI - USB 3)", "Second", buttons=("Yes",))
    results = window("Results", buttons=("OK",))
    supervisor = SequenceSupervisor(
        tmp_path,
        [[device], [prompt], [results]],
        ["Tests run (4), Failures (0)"],
    )

    outcome = supervisor.monitor_test(
        [DialogRule(1, "First"), DialogRule(2, "Second", "Yes")],
        "0984",
        "1410",
        baseline_log=("old",),
    )

    assert outcome.summary_values() == [4, 0, "Pass"]
    assert (prompt.title, "Yes", "test prompt") in supervisor.clicked
    assert (results.title, "OK", "results acknowledgement") in supervisor.clicked


def test_completed_compliance_failure_returns_without_diagnostics_or_reconnect(
    tmp_path: Path,
) -> None:
    device = window(
        "USB Command Verifier (xHCI - USB 3)",
        "VID=0984 PID=1410",
        has_list_box=True,
    )
    results = window("Results", "complete", buttons=("OK",))
    main = window("USB 3 Gen X Command Verifier")
    supervisor = SequenceSupervisor(
        tmp_path,
        [[device], [results], [main]],
        [
            "Stopping Test [ L1Suspend/Resume Test (Configuration Index 0):\n"
            " Number of: Fails (1); Aborts (0) ]",
            "TEST RESULTS: [ Passed (35); Failed (1) ]",
        ],
    )

    outcome = supervisor.monitor_test([], "0984", "1410")

    assert outcome.summary_values() == [36, 1, "Fail"]
    assert not outcome.reconnect_required
    assert outcome.reason == ""
    assert list(tmp_path.iterdir()) == []


def test_monitor_failure_preempts_and_returns_null_count_failure(tmp_path: Path) -> None:
    device = window(
        "USB Command Verifier (xHCI - USB 3)",
        "Select device",
        has_list_box=True,
    )
    failure = window("Failure Details", "The test failed", buttons=("OK",))
    supervisor = SequenceSupervisor(tmp_path, [[device], [failure]], [])

    outcome = supervisor.monitor_test([], "0984", "1410")

    assert outcome.summary_values() == [None, None, "Fail"]
    assert supervisor.clicked == [(failure.title, "OK", "failure acknowledgement")]
    assert list(tmp_path.iterdir()) == []


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
    supervisor = SequenceSupervisor(tmp_path, [[results]], ["Tests run (4), Failures (0)"])

    outcome = supervisor.monitor_test([], "0984", "1410", baseline_log=("old",))

    assert outcome.retry_required
    assert outcome.tests_run is None
    assert outcome.failures is None
    assert (results.title, "OK", "invalid device-selection attempt") in supervisor.clicked
    assert list(tmp_path.iterdir()) == []


def test_missing_dut_in_device_list_returns_retry_without_artifacts(
    tmp_path: Path,
) -> None:
    class MissingDUTSupervisor(SequenceSupervisor):
        def select_device(self, window, vendor_id, product_id):
            return False

    device = window(
        "USB Command Verifier (xHCI - USB 3)",
        "Select device",
        has_list_box=True,
    )
    supervisor = MissingDUTSupervisor(tmp_path, [[device]], [])

    outcome = supervisor.monitor_test([], "0984", "1410")

    assert outcome.retry_required
    assert "not available" in outcome.reason
    assert list(tmp_path.iterdir()) == []
