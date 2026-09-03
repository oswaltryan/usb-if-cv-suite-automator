"""Fault-tolerant CV Suite window discovery and dialog handling."""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterable

from .logging_config import timestamped_prompt


MAIN_WINDOW_TITLE = "USB 3 Gen X Command Verifier"
COMMAND_DIALOG_TITLE = "USB Command Verifier (xHCI - USB 3)"
RESULTS_WINDOW_TITLE = "Results"
LOG_CONTROL_ID = 1007

logger = logging.getLogger(__name__)


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


@dataclass(frozen=True)
class TestOutcome:
    tests_run: int | None
    failures: int | None
    status: str
    reason: str = ""

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
        failure_body = (
            not window.is_main_window
            and re.search(r"\b(test failed|test has failed|failure detected)\b", text)
        )
        if not window.is_main_window and (
            failure_title
            or failure_body
            or any(message in text for message in failures)
        ):
            return UIEvent(EventKind.FAILURE, window, reason=window.searchable_text)

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
            if (
                window.title.casefold() == COMMAND_DIALOG_TITLE.casefold()
                and window.has_list_box
            ):
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


def latest_failed_test_name(lines: Iterable[str]) -> str | None:
    """Return the most recent named subtest whose stop record reports failures."""
    log_text = "\n".join(lines)
    pattern = re.compile(
        r"Stopping Test\s*\[\s*(.+?):\s*\r?\n\s*"
        r"Number of:\s*Fails\s*\(([1-9]\d*)\)",
        re.IGNORECASE,
    )
    matches = pattern.findall(log_text)
    return matches[-1][0].strip() if matches else None


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
        diagnostics_root: Path,
        failure_messages: Iterable[str],
        operator_input: Callable[[str], str] = input,
        poll_interval: float = 0.5,
        inactivity_timeout: float = 300,
    ) -> None:
        self.app = app
        self.main_window = main_window
        self.log_window = log_window
        self.diagnostics_root = diagnostics_root
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
            logger.exception(
                "Warning: CV Suite could not be brought to the foreground: %s", exc
            )

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
                    f"The CV Suite main window did not become ready after {phase}.",
                    context={"phase": phase},
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
            self.operator_checkpoint(
                f"CV Suite windows could not be inspected: {exc}", []
            )
            self.reconnect()
            return [self._snapshot_window(window) for window in self.app.windows()]

    def reconnect(self) -> None:
        """Reconnect after CV Suite is restarted or existing handles go stale."""
        while True:
            try:
                self.app = type(self.app)().connect(
                    title=MAIN_WINDOW_TITLE, timeout=5
                )
                self.main_window = self.app.window(best_match=MAIN_WINDOW_TITLE)
                self.log_window = self.main_window.child_window(
                    control_id=LOG_CONTROL_ID
                )
                if self.main_window.exists(timeout=2):
                    return
            except Exception as exc:
                self.operator_checkpoint(
                    f"Could not reconnect to CV Suite: {exc}", []
                )

    def _log_lines(self) -> list[str]:
        try:
            return list(self.log_window.texts())
        except Exception:
            return []

    def capture_diagnostics(
        self,
        reason: str,
        snapshots: Iterable[WindowSnapshot],
        context: dict[str, Any] | None = None,
    ) -> Path:
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        context = context or {}
        label_parts = [stamp]
        if context.get("controller"):
            label_parts.append(str(context["controller"]))
        if context.get("protocol") is not None:
            label_parts.append(f"USB{context['protocol']}")
        if context.get("test") is not None:
            label_parts.append(f"test-{context['test']}")
        label = re.sub(r"[^A-Za-z0-9_.-]+", "-", "-".join(label_parts))
        incident_dir = self.diagnostics_root / label
        try:
            incident_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            incident_dir = Path.cwd() / "cv-suite-diagnostics" / label
            try:
                incident_dir.mkdir(parents=True, exist_ok=True)
            except OSError as fallback_exc:
                logger.error(
                    "Warning: diagnostics could not be created at the session "
                    "location (%s) or local fallback (%s).",
                    exc,
                    fallback_exc,
                )
                return Path("diagnostics-unavailable")
        windows = list(snapshots)
        payload = {
            "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
            "reason": reason,
            "context": context,
            "windows": [
                {
                    "handle": window.handle,
                    "title": window.title,
                    "texts": list(window.texts),
                    "buttons": list(window.buttons),
                    "has_list_box": window.has_list_box,
                    "visible": window.visible,
                    "enabled": window.enabled,
                    "class_name": window.class_name,
                }
                for window in windows
            ],
            "log_tail": self._log_lines()[-30:],
        }
        try:
            (incident_dir / "incident.json").write_text(
                json.dumps(payload, indent=2), encoding="utf-8"
            )
        except OSError as exc:
            logger.exception("Warning: incident text could not be saved: %s", exc)
        visible_windows = [window for window in windows if window.visible]
        for index, window in enumerate(visible_windows, start=1):
            if window.wrapper is None:
                continue
            try:
                if window.is_main_window:
                    self._reveal_failed_test(window.wrapper)
                image = window.wrapper.capture_as_image()
                image.save(incident_dir / f"window-{index}.png")
            except Exception:
                pass
        return incident_dir

    def _reveal_failed_test(self, main_window: Any) -> bool:
        """Best-effort scroll of the CV Suite test tree before a screenshot."""
        failed_name = latest_failed_test_name(self._log_lines())
        if not failed_name:
            return False
        expected = " ".join(failed_name.split()).casefold()

        try:
            controls = main_window.descendants()
        except Exception:
            return False
        for control in controls:
            try:
                if control.friendly_class_name() != "TreeView":
                    continue
                items = []
                for root in control.roots():
                    items.append(root)
                    items.extend(root.sub_elements())
                for item in items:
                    actual = " ".join(item.text().split()).casefold()
                    if actual == expected or expected in actual or actual in expected:
                        item.ensure_visible()
                        return True
            except Exception:
                continue
        return False

    def operator_checkpoint(
        self,
        reason: str,
        snapshots: Iterable[WindowSnapshot] | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        windows = list(snapshots) if snapshots is not None else self.snapshots()
        location = self.capture_diagnostics(reason, windows, context)
        print()
        logger.info("%s", "=" * 70)
        logger.info("OPERATOR ACTION REQUIRED")
        logger.info("%s", reason)
        logger.info("Diagnostics: %s", location)
        logger.info("Correct the condition, then return to this window.")
        logger.info("%s", "=" * 70)
        self.operator_input(
            timestamped_prompt("Press ENTER to rescan and continue: ")
        )
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
        context: dict[str, Any] | None = None,
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
                    self.operator_checkpoint(
                        f"Could not complete {phase} after 3 attempts: {exc}",
                        context={"phase": phase, **(context or {})},
                    )
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
                    self.app.window(handle=current.handle).child_window(
                        best_match=button
                    ).click()
                    return
                except Exception:
                    attempts += 1
            if attempts >= 3 or time.monotonic() >= deadline:
                self.operator_checkpoint(
                    f"Could not click '{button}' during {phase} after 3 attempts.",
                    self.snapshots(),
                    {"phase": phase, "button": button},
                )
                attempts = 0
                deadline = time.monotonic() + 60
            time.sleep(self.poll_interval)

    def select_device(
        self, window: WindowSnapshot, vendor_id: str, product_id: str
    ) -> bool:
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
        context: dict[str, Any],
        reason: str,
    ) -> TestOutcome:
        location = self.capture_diagnostics(reason, self.snapshots(), context)
        self.dismiss_window(window, "invalid device-selection attempt")
        return TestOutcome(
            None,
            None,
            "Retry",
            f"{reason}; diagnostics saved to {location}",
        )

    def prepare_for_test_retry(self, context: dict[str, Any]) -> None:
        """Dismiss residue from an abandoned selection and restore the main UI."""
        deadline = time.monotonic() + 60
        while True:
            windows = self.snapshots()
            blocking = [
                window for window in windows
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
                        window for window in windows
                        if window.is_main_window and window.visible and window.enabled
                    ),
                    None,
                )
                if main is not None:
                    self.main_window = self.app.window(handle=main.handle)
                    self.log_window = self.main_window.child_window(
                        control_id=LOG_CONTROL_ID
                    )
                    self.focus_main_window()
                    return
                if blocking:
                    self.operator_checkpoint(
                        f"Cannot retry while '{blocking[0].title}' is blocking CV Suite.",
                        windows,
                        context,
                    )

            if time.monotonic() >= deadline:
                self.operator_checkpoint(
                    "CV Suite did not return to its main window for test reselection.",
                    windows,
                    context,
                )
                deadline = time.monotonic() + 60
            time.sleep(self.poll_interval)

    def monitor_test(
        self,
        rules: Iterable[DialogRule],
        vendor_id: str,
        product_id: str,
        context: dict[str, Any],
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

            signature = repr(
                ([(w.title, w.texts) for w in windows], self._log_lines()[-5:])
            )
            if signature != last_signature:
                last_signature = signature
                last_progress = time.monotonic()

            if event.kind is EventKind.FAILURE:
                if not device_selected and event.window is not None:
                    return self._retry_missing_dut(
                        event.window,
                        context,
                        "CV Suite failed before the exact DUT was selected",
                    )
                location = self.capture_diagnostics(event.reason, windows, context)
                if event.window is not None:
                    safe_buttons = {"ok", "close"}
                    for button in event.window.buttons:
                        if button.replace("&", "").strip().casefold() in safe_buttons:
                            self.click_button(
                                event.window, button, "failure acknowledgement"
                            )
                            break
                current_log = self._log_lines()
                parsed = (
                    parse_log_results(current_log)
                    if tuple(current_log) != baseline_log
                    else None
                )
                return TestOutcome(
                    parsed.tests_run if parsed and parsed.failures else None,
                    parsed.failures if parsed and parsed.failures else None,
                    "Fail",
                    f"CV Suite failure; diagnostics saved to {location}",
                )

            if event.kind is EventKind.RESULTS and event.window is not None:
                if not device_selected:
                    return self._retry_missing_dut(
                        event.window,
                        context,
                        "CV Suite produced results before the exact DUT was selected",
                    )
                result_deadline = time.monotonic() + 10
                current_log = self._log_lines()
                while tuple(current_log) == baseline_log and time.monotonic() < result_deadline:
                    time.sleep(self.poll_interval)
                    current_log = self._log_lines()
                outcome = (
                    parse_log_results(current_log)
                    if tuple(current_log) != baseline_log
                    else None
                )
                self.click_button(event.window, "OK", "results acknowledgement")
                self.wait_for_main_window("results acknowledgement")
                if outcome is not None:
                    return outcome
                location = self.capture_diagnostics(
                    "Results appeared without parseable test counts", windows, context
                )
                return TestOutcome(
                    None,
                    None,
                    "Fail",
                    f"Missing result counts; diagnostics saved to {location}",
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
                    context,
                    f"DUT VID {vendor_id} / PID {product_id} was not available "
                    "in the CV Suite device list",
                )

            elif event.kind is EventKind.UNKNOWN:
                signature = repr((event.window.title, event.window.texts))
                if signature != unknown_signature:
                    unknown_signature = signature
                    unknown_since = time.monotonic()
                elif time.monotonic() - unknown_since >= 3:
                    self.operator_checkpoint(event.reason, windows, context)
                    unknown_signature = ""
                    last_progress = time.monotonic()

            elif time.monotonic() - last_progress >= self.inactivity_timeout:
                self.operator_checkpoint(
                    "CV Suite showed no window or log progress for 5 minutes.",
                    windows,
                    context,
                )
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
                failure_body = (
                    not window.is_main_window
                    and re.search(
                        r"\b(test failed|test has failed|failure detected)\b",
                        searchable,
                    )
                )
                known_failure = (
                    title != MAIN_WINDOW_TITLE.casefold()
                    and any(
                        message.casefold() in searchable
                        for message in self.failure_messages
                    )
                )
                if not window.is_main_window and (
                    failure_title or failure_body or known_failure
                ):
                    self.operator_checkpoint(
                        f"CV Suite reported a failure during {phase}.", windows, {"phase": phase}
                    )
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
                            f"Unexpected window appeared during {phase}: {unknown[0].title}",
                            windows,
                            {"phase": phase},
                        )
                        unknown_signature = ""
                        deadline = time.monotonic() + 60
                elif time.monotonic() >= deadline:
                    self.operator_checkpoint(
                        f"Timed out waiting for the expected CV Suite prompt during {phase}.",
                        windows,
                        {"phase": phase, "expected_text": text},
                    )
                    deadline = time.monotonic() + 60
                else:
                    unknown_signature = ""
            time.sleep(self.poll_interval)
