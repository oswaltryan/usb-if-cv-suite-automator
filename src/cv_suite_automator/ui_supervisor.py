"""Fault-tolerant CV Suite window discovery and dialog handling."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Iterable

from .logging_config import timestamped_prompt


MAIN_WINDOW_TITLE = "USB 3 Gen X Command Verifier"
COMMAND_DIALOG_TITLE = "USB Command Verifier (xHCI - USB 3)"
RESULTS_WINDOW_TITLE = "Results"
LOG_CONTROL_ID = 1007

logger = logging.getLogger(__name__)


def _appended_log_text(current_lines: Iterable[str], baseline_lines: Iterable[str]) -> str:
    """Return text appended to a CV Suite log snapshot."""
    current = list(current_lines)
    baseline = list(baseline_lines)
    if current[: len(baseline)] == baseline:
        return "\n".join(current[len(baseline) :])

    current_text = "\n".join(current)
    baseline_text = "\n".join(baseline)
    if current_text.startswith(baseline_text):
        return current_text[len(baseline_text) :].lstrip("\r\n")
    return current_text


class EventKind(Enum):
    FAILURE = "failure"
    RESULTS = "results"
    PROMPT = "prompt"
    DEVICE_SELECTION = "device_selection"
    UNKNOWN = "unknown"
    IDLE = "idle"


@dataclass(frozen=True)
class DialogRule:
    key: int
    text: str
    button: str = "OK"
    repeatable: bool = False


@dataclass
class WindowSnapshot:
    handle: int
    title: str
    texts: tuple[str, ...]
    buttons: tuple[str, ...] = ()
    has_list_box: bool = False
    visible: bool = True
    enabled: bool = True
    class_name: str = ""
    wrapper: Any = field(default=None, repr=False, compare=False)

    @property
    def searchable_text(self) -> str:
        return "\n".join((self.title, *self.texts))

    @property
    def is_main_window(self) -> bool:
        return self.title.casefold().startswith(MAIN_WINDOW_TITLE.casefold())


@dataclass(frozen=True)
class UIEvent:
    kind: EventKind
    window: WindowSnapshot | None = None
    rule: DialogRule | None = None
    reason: str = ""
    reconnect_required: bool = False


@dataclass(frozen=True)
class TestOutcome:
    tests_run: int | None
    failures: int | None
    status: str
    reason: str = ""
    reconnect_required: bool = False

    @property
    def failed(self) -> bool:
        return self.status == "Fail"

    @property
    def retry_required(self) -> bool:
        return self.status == "Retry"

    def summary_values(self) -> list[int | str | None]:
        return [self.tests_run, self.failures, self.status]


def classify_windows(
    snapshots: Iterable[WindowSnapshot],
    rules: Iterable[DialogRule],
    handled_rule_keys: set[int],
    failure_messages: Iterable[str],
    device_selected: bool,
) -> UIEvent:
    """Classify the most important event in a CV Suite window snapshot."""
    windows = [window for window in snapshots if window.visible]
    failures = tuple(message.casefold() for message in failure_messages)

    for window in windows:
        title = window.title.casefold()
        text = window.searchable_text.casefold()
        failure_title = re.search(r"\b(error|failure|failed)\b", title)
        failure_body = not window.is_main_window and re.search(
            r"\b(test failed|test has failed|failure detected)\b", text
        )
        known_device_failure = any(message in text for message in failures)
        if not window.is_main_window and (failure_title or failure_body or known_device_failure):
            return UIEvent(
                EventKind.FAILURE,
                window,
                reason=window.searchable_text,
                reconnect_required=known_device_failure,
            )

    for window in windows:
        if window.title.casefold() == RESULTS_WINDOW_TITLE.casefold():
            return UIEvent(EventKind.RESULTS, window)

    for window in windows:
        if window.is_main_window:
            continue
        text = window.searchable_text.casefold()
        for rule in rules:
            if rule.text.casefold() in text and (
                rule.repeatable or rule.key not in handled_rule_keys
            ):
                return UIEvent(EventKind.PROMPT, window, rule=rule)

    if not device_selected:
        for window in windows:
            if window.title.casefold() == COMMAND_DIALOG_TITLE.casefold() and window.has_list_box:
                return UIEvent(EventKind.DEVICE_SELECTION, window)

    for window in windows:
        if window.title and not window.is_main_window:
            # A prompt can remain visible briefly after its button is clicked.
            # Treat that as an in-flight transition instead of an unknown popup.
            searchable = window.searchable_text.casefold()
            if any(rule.text.casefold() in searchable for rule in rules):
                continue
            return UIEvent(
                EventKind.UNKNOWN,
                window,
                reason=f"Unrecognized blocking window: {window.title}",
            )

    return UIEvent(EventKind.IDLE)


def parse_log_results(lines: Iterable[str]) -> TestOutcome | None:
    """Return the latest complete CV Suite result line, if one exists."""
    legacy_pattern = re.compile(
        r"Tests\s+run\s*\((\d+)\).*?Failures\s*\((\d+)\)",
        re.IGNORECASE,
    )
    current_pattern = re.compile(
        r"Passed\s*\((\d+)\)\s*;\s*Failed\s*\((\d+)\)",
        re.IGNORECASE,
    )
    for line in reversed(list(lines)):
        match = current_pattern.search(line)
        if match:
            passed, failures = (int(value) for value in match.groups())
            return TestOutcome(
                passed + failures,
                failures,
                "Pass" if failures == 0 else "Fail",
            )
        match = legacy_pattern.search(line)
        if match:
            tests_run, failures = (int(value) for value in match.groups())
            return TestOutcome(
                tests_run,
                failures,
                "Pass" if failures == 0 else "Fail",
            )
    return None


def device_item_matches(item: str, vendor_id: str, product_id: str) -> bool:
    """Return whether a CV Suite list item identifies the exact DUT."""
    vendor_id = vendor_id.casefold().removeprefix("0x")
    product_id = product_id.casefold().removeprefix("0x")
    vid = re.search(r"\bvid\s*[:=_-]?\s*(?:0x)?([0-9a-f]{4})\b", item, re.I)
    pid = re.search(r"\bpid\s*[:=_-]?\s*(?:0x)?([0-9a-f]{4})\b", item, re.I)
    return bool(
        vid
        and pid
        and vid.group(1).casefold() == vendor_id
        and pid.group(1).casefold() == product_id
    )


class CVSuiteUISupervisor:
    """Observe and operate CV Suite without relying on a fixed dialog order."""

    def __init__(
        self,
        app: Any,
        main_window: Any,
        log_window: Any,
        failure_messages: Iterable[str],
        operator_input: Callable[[str], str] = input,
        poll_interval: float = 0.5,
        inactivity_timeout: float = 300,
    ) -> None:
        self.app = app
        self.main_window = main_window
        self.log_window = log_window
        self.failure_messages = tuple(failure_messages)
        self.operator_input = operator_input
        self.poll_interval = poll_interval
        self.inactivity_timeout = inactivity_timeout

    def focus_main_window(self) -> None:
        """Best-effort foreground activation without turning focus into a failure."""
        try:
            if self.main_window.is_minimized():
                self.main_window.restore()
            self.main_window.set_focus()
        except Exception as exc:
            logger.exception("Warning: CV Suite could not be brought to the foreground: %s", exc)

    def wait_for_main_window(self, phase: str) -> None:
        """Wait for a dismissed modal to release the main window, then focus it."""
        deadline = time.monotonic() + 60
        while True:
            try:
                main_window = self.app.window(title=MAIN_WINDOW_TITLE)
                if (
                    main_window.exists(timeout=1)
                    and main_window.is_visible()
                    and main_window.is_enabled()
                ):
                    self.main_window = main_window
                    self.log_window = main_window.child_window(control_id=LOG_CONTROL_ID)
                    self.focus_main_window()
                    return
            except Exception:
                pass

            if time.monotonic() >= deadline:
                self.operator_checkpoint(
                    f"The CV Suite main window did not become ready after {phase}."
                )
                deadline = time.monotonic() + 60
            time.sleep(self.poll_interval)

    def _snapshot_window(self, window: Any) -> WindowSnapshot:
        texts: list[str] = []
        buttons: list[str] = []
        has_list_box = False
        try:
            title = window.window_text()
        except Exception:
            title = ""
        try:
            descendants = window.descendants()
        except Exception:
            descendants = []
        for control in descendants:
            try:
                control_text = control.window_text().strip()
                control_type = control.friendly_class_name()
            except Exception:
                continue
            if control_text and control_text not in texts:
                texts.append(control_text)
            if control_type == "Button" and control_text:
                buttons.append(control_text)
            elif control_type == "ListBox":
                has_list_box = True
        try:
            handle = int(window.handle)
        except Exception:
            handle = id(window)
        try:
            visible = bool(window.is_visible())
        except Exception:
            visible = False
        try:
            enabled = bool(window.is_enabled())
        except Exception:
            enabled = False
        try:
            class_name = window.class_name()
        except Exception:
            class_name = ""
        return WindowSnapshot(
            handle=handle,
            title=title,
            texts=tuple(texts),
            buttons=tuple(buttons),
            has_list_box=has_list_box,
            visible=visible,
            enabled=enabled,
            class_name=class_name,
            wrapper=window,
        )

    def snapshots(self) -> list[WindowSnapshot]:
        try:
            return [self._snapshot_window(window) for window in self.app.windows()]
        except Exception as exc:
            self.operator_checkpoint(f"CV Suite windows could not be inspected: {exc}")
            self.reconnect()
            return [self._snapshot_window(window) for window in self.app.windows()]

    def reconnect(self) -> None:
        """Reconnect after CV Suite is restarted or existing handles go stale."""
        while True:
            try:
                self.app = type(self.app)().connect(title=MAIN_WINDOW_TITLE, timeout=5)
                self.main_window = self.app.window(best_match=MAIN_WINDOW_TITLE)
                self.log_window = self.main_window.child_window(control_id=LOG_CONTROL_ID)
                if self.main_window.exists(timeout=2):
                    return
            except Exception as exc:
                self.operator_checkpoint(f"Could not reconnect to CV Suite: {exc}")

    def _log_lines(self) -> list[str]:
        try:
            return list(self.log_window.texts())
        except Exception:
            return []

    def wait_for_suite_ready(
        self,
        test_index: int,
        baseline_log: tuple[str, ...],
        validation_required: bool,
        timeout: float = 60,
    ) -> tuple[str, ...]:
        """Wait until CV Suite has validated and rendered the selected suite."""
        deadline = time.monotonic() + timeout
        stable_polls = 0
        while time.monotonic() < deadline:
            try:
                selected = tuple(
                    self.main_window.child_window(control_id=1001)
                    .wrapper_object()
                    .selected_indices()
                )
                tree_count = (
                    self.main_window.child_window(control_id=1002).wrapper_object().item_count()
                )
                run_enabled = self.main_window.child_window(control_id=1013).is_enabled()
                current_log = tuple(self._log_lines())
                validation_complete = not validation_required or (
                    "Validation succeeded!" in _appended_log_text(current_log, baseline_log)
                )
                ready = (
                    test_index in selected
                    and tree_count > 0
                    and run_enabled
                    and validation_complete
                )
            except Exception:
                ready = False
                current_log = tuple(self._log_lines())

            stable_polls = stable_polls + 1 if ready else 0
            if stable_polls >= 2:
                return current_log
            time.sleep(self.poll_interval)

        raise TimeoutError("CV Suite did not finish validating the selected test suite")

    def wait_for_test_launch(self, baseline_log: tuple[str, ...], timeout: float = 20) -> None:
        """Confirm that clicking Run caused CV Suite to begin a test launch."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            windows = self.snapshots()
            if any(window.visible and not window.is_main_window for window in windows):
                return
            if any(
                window.is_main_window and window.title.casefold() != MAIN_WINDOW_TITLE.casefold()
                for window in windows
            ):
                return
            appended = _appended_log_text(self._log_lines(), baseline_log).casefold()
            if "now starting test" in appended or "select single item" in appended:
                return
            time.sleep(self.poll_interval)

        raise TimeoutError("CV Suite did not respond after Run was clicked")

    def operator_checkpoint(self, reason: str) -> None:
        print()
        logger.info("%s", "=" * 70)
        logger.info("OPERATOR ACTION REQUIRED")
        logger.info("%s", reason)
        logger.info("Correct the condition, then return to this window.")
        logger.info("%s", "=" * 70)
        self.operator_input(timestamped_prompt("Press ENTER to rescan and continue: "))
        self.focus_main_window()

    def _find_current(self, original: WindowSnapshot) -> WindowSnapshot | None:
        for window in self.snapshots():
            if window.handle == original.handle:
                return window
        for window in self.snapshots():
            if window.title == original.title:
                return window
        return None

    def perform_action(
        self,
        action: Callable[[], Any],
        phase: str,
    ) -> Any:
        """Retry a safe UI action before escalating it to the operator."""
        attempts = 0
        deadline = time.monotonic() + 60
        while True:
            try:
                return action()
            except Exception as exc:
                attempts += 1
                if attempts >= 3 or time.monotonic() >= deadline:
                    self.operator_checkpoint(f"Could not complete {phase} after 3 attempts: {exc}")
                    attempts = 0
                    deadline = time.monotonic() + 60
                time.sleep(self.poll_interval)

    def click_button(self, window: WindowSnapshot, button: str, phase: str) -> None:
        deadline = time.monotonic() + 60
        attempts = 0
        while True:
            current = self._find_current(window)
            if current is not None:
                try:
                    self.app.window(handle=current.handle).child_window(best_match=button).click()
                    return
                except Exception:
                    attempts += 1
            if attempts >= 3 or time.monotonic() >= deadline:
                self.operator_checkpoint(
                    f"Could not click '{button}' during {phase} after 3 attempts."
                )
                attempts = 0
                deadline = time.monotonic() + 60
            time.sleep(self.poll_interval)

    def select_device(self, window: WindowSnapshot, vendor_id: str, product_id: str) -> bool:
        current = self._find_current(window)
        if current is None:
            return False
        try:
            window_spec = self.app.window(handle=current.handle)
            list_box = window_spec.child_window(best_match="ListBox")
            for index, item in enumerate(list_box.texts()):
                if device_item_matches(item, vendor_id, product_id):
                    list_box.select(max(0, index - 1))
                    self.click_button(current, "Ok", "device selection")
                    return True
        except Exception:
            return False
        return False

    def dismiss_window(self, window: WindowSnapshot, phase: str) -> None:
        """Close a modal without accepting its current selection or result."""
        for candidate in ("Cancel", "Abort", "Close", "OK"):
            for button in window.buttons:
                if button.replace("&", "").strip().casefold() == candidate.casefold():
                    self.click_button(window, button, phase)
                    return
        current = self._find_current(window)
        if current is not None:
            try:
                self.app.window(handle=current.handle).close()
            except Exception:
                pass

    def _retry_missing_dut(
        self,
        window: WindowSnapshot,
        reason: str,
    ) -> TestOutcome:
        self.dismiss_window(window, "invalid device-selection attempt")
        return TestOutcome(None, None, "Retry", reason)

    def prepare_for_test_retry(self) -> None:
        """Dismiss residue from an abandoned selection and restore the main UI."""
        deadline = time.monotonic() + 60
        while True:
            windows = self.snapshots()
            blocking = [
                window
                for window in windows
                if window.visible and not window.is_main_window and window.title
            ]
            for window in blocking:
                if (
                    window.title.casefold() == RESULTS_WINDOW_TITLE.casefold()
                    or window.title.casefold() == COMMAND_DIALOG_TITLE.casefold()
                    or re.search(r"\b(error|failure|failed)\b", window.title, re.I)
                ):
                    self.dismiss_window(window, "selection retry cleanup")
                    break
            else:
                main = next(
                    (
                        window
                        for window in windows
                        if window.is_main_window and window.visible and window.enabled
                    ),
                    None,
                )
                if main is not None:
                    self.main_window = self.app.window(handle=main.handle)
                    self.log_window = self.main_window.child_window(control_id=LOG_CONTROL_ID)
                    self.focus_main_window()
                    return
                if blocking:
                    self.operator_checkpoint(
                        f"Cannot retry while '{blocking[0].title}' is blocking CV Suite."
                    )

            if time.monotonic() >= deadline:
                self.operator_checkpoint(
                    "CV Suite did not return to its main window for test reselection."
                )
                deadline = time.monotonic() + 60
            time.sleep(self.poll_interval)

    def monitor_test(
        self,
        rules: Iterable[DialogRule],
        vendor_id: str,
        product_id: str,
        baseline_log: tuple[str, ...] = (),
    ) -> TestOutcome:
        rules = tuple(rules)
        handled: set[int] = set()
        device_selected = False
        last_signature = ""
        last_progress = time.monotonic()
        unknown_signature = ""
        unknown_since = 0.0

        while True:
            windows = self.snapshots()
            event = classify_windows(
                windows,
                rules,
                handled,
                self.failure_messages,
                device_selected,
            )

            signature = repr(([(w.title, w.texts) for w in windows], self._log_lines()[-5:]))
            if signature != last_signature:
                last_signature = signature
                last_progress = time.monotonic()

            if event.kind is EventKind.FAILURE:
                if not device_selected and event.window is not None:
                    return self._retry_missing_dut(
                        event.window,
                        "CV Suite failed before the exact DUT was selected",
                    )
                if event.window is not None:
                    safe_buttons = {"ok", "close"}
                    for button in event.window.buttons:
                        if button.replace("&", "").strip().casefold() in safe_buttons:
                            self.click_button(event.window, button, "failure acknowledgement")
                            break
                current_log = self._log_lines()
                parsed = (
                    parse_log_results(current_log) if tuple(current_log) != baseline_log else None
                )
                return TestOutcome(
                    parsed.tests_run if parsed and parsed.failures else None,
                    parsed.failures if parsed and parsed.failures else None,
                    "Fail",
                    "CV Suite reported a failure",
                    reconnect_required=event.reconnect_required,
                )

            if event.kind is EventKind.RESULTS and event.window is not None:
                if not device_selected:
                    return self._retry_missing_dut(
                        event.window,
                        "CV Suite produced results before the exact DUT was selected",
                    )
                result_deadline = time.monotonic() + 10
                current_log = self._log_lines()
                while tuple(current_log) == baseline_log and time.monotonic() < result_deadline:
                    time.sleep(self.poll_interval)
                    current_log = self._log_lines()
                outcome = (
                    parse_log_results(current_log) if tuple(current_log) != baseline_log else None
                )
                self.click_button(event.window, "OK", "results acknowledgement")
                self.wait_for_main_window("results acknowledgement")
                if outcome is not None:
                    return outcome
                return TestOutcome(
                    None,
                    None,
                    "Fail",
                    "Results appeared without parseable test counts",
                )

            if event.kind is EventKind.PROMPT and event.window and event.rule:
                self.click_button(event.window, event.rule.button, "test prompt")
                if not event.rule.repeatable:
                    handled.add(event.rule.key)
                last_progress = time.monotonic()
                continue

            if event.kind is EventKind.DEVICE_SELECTION and event.window:
                if self.select_device(event.window, vendor_id, product_id):
                    device_selected = True
                    last_progress = time.monotonic()
                    continue
                return self._retry_missing_dut(
                    event.window,
                    f"DUT VID {vendor_id} / PID {product_id} was not available "
                    "in the CV Suite device list",
                )

            elif event.kind is EventKind.UNKNOWN and event.window is not None:
                signature = repr((event.window.title, event.window.texts))
                if signature != unknown_signature:
                    unknown_signature = signature
                    unknown_since = time.monotonic()
                elif time.monotonic() - unknown_since >= 3:
                    self.operator_checkpoint(event.reason)
                    unknown_signature = ""
                    last_progress = time.monotonic()

            elif time.monotonic() - last_progress >= self.inactivity_timeout:
                self.operator_checkpoint("CV Suite showed no window or log progress for 5 minutes.")
                last_progress = time.monotonic()

            if event.kind is not EventKind.UNKNOWN:
                unknown_signature = ""

            time.sleep(self.poll_interval)

    def wait_for_text_and_click(self, text: str, button: str, phase: str) -> None:
        deadline = time.monotonic() + 60
        unknown_signature = ""
        unknown_since = 0.0
        while True:
            windows = self.snapshots()
            for window in windows:
                title = window.title.casefold()
                searchable = window.searchable_text.casefold()
                failure_title = re.search(r"\b(error|failure|failed)\b", title)
                failure_body = not window.is_main_window and re.search(
                    r"\b(test failed|test has failed|failure detected)\b",
                    searchable,
                )
                known_failure = title != MAIN_WINDOW_TITLE.casefold() and any(
                    message.casefold() in searchable for message in self.failure_messages
                )
                if not window.is_main_window and (failure_title or failure_body or known_failure):
                    self.operator_checkpoint(f"CV Suite reported a failure during {phase}.")
                    deadline = time.monotonic() + 60
                    break
                if text.casefold() in searchable:
                    self.click_button(window, button, phase)
                    return
            else:
                unknown = [
                    window
                    for window in windows
                    if window.visible and window.title and not window.is_main_window
                ]
                if unknown:
                    signature = repr((unknown[0].title, unknown[0].texts))
                    if signature != unknown_signature:
                        unknown_signature = signature
                        unknown_since = time.monotonic()
                    elif time.monotonic() - unknown_since >= 3:
                        self.operator_checkpoint(
                            f"Unexpected window appeared during {phase}: {unknown[0].title}"
                        )
                        unknown_signature = ""
                        deadline = time.monotonic() + 60
                elif time.monotonic() >= deadline:
                    self.operator_checkpoint(
                        f"Timed out waiting for the expected CV Suite prompt during {phase}."
                    )
                    deadline = time.monotonic() + 60
                else:
                    unknown_signature = ""
            time.sleep(self.poll_interval)
