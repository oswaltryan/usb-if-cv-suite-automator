"""Interactive configuration for a CV Suite automation run."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from .logging_config import timestamped_prompt

logger = logging.getLogger(__name__)
TEST_OPTIONS = (
    ("chapter9", "Chapter 9 Tests"),
    ("connector", "Connector Type Tests"),
    ("summary", "Device Summary"),
    ("msc", "MSC Tests"),
)
UASP_OPTION = ("uasp", "UASP Tests")
CONTROLLER_OPTIONS = (("ASMedia", "ASMedia"), ("Intel", "Intel"))
USB2_PROTOCOL = 2
USB3_PROTOCOL = 3
PROTOCOL_OPTIONS = ((USB2_PROTOCOL, "USB2"), (USB3_PROTOCOL, "USB3"))
INVALID_MANUFACTURER_CHARACTERS = frozenset('<>:"/\\|?*')
MINIMUM_PRINTABLE_CODEPOINT = 32


@dataclass(frozen=True)
class RunSelection:
    tests: tuple[str, ...]
    controllers: tuple[str, ...]
    protocols: tuple[int, ...]
    storage_manufacturer: str

    def test_ids(self, protocol: int) -> tuple[int, ...]:
        mapping = {
            "chapter9": 1 if protocol == USB2_PROTOCOL else 2,
            "connector": 3,
            "summary": 6,
            "msc": 17,
            "uasp": 21,
        }
        return tuple(mapping[test] for test in self.tests)


def _prompt_numbered[Choice](
    title: str,
    options: Iterable[tuple[Choice, str]],
    input_func: Callable[[str], str],
) -> tuple[Choice, ...]:
    choices = tuple(options)
    while True:
        print()
        logger.info("%s (press ENTER for ALL)", title)
        for number, (_, label) in enumerate(choices, start=1):
            logger.info("%d. %s", number, label)
        response = input_func(timestamped_prompt("Selection: ")).strip()
        if not response:
            return tuple(value for value, _ in choices)
        try:
            numbers = [int(part) for part in response.split()]
        except ValueError:
            logger.warning("Enter space-separated numbers from the list, or press ENTER for ALL.")
            continue
        if not numbers or any(number < 1 or number > len(choices) for number in numbers):
            logger.warning("One or more selections are outside the numbered list.")
            continue
        selected = set(numbers)
        return tuple(
            value for number, (value, _) in enumerate(choices, start=1) if number in selected
        )


def _prompt_storage_manufacturer(input_func: Callable[[str], str]) -> str:
    while True:
        print()
        response = " ".join(input_func(timestamped_prompt("Storage Manufacturer: ")).split())
        has_invalid_character = any(
            character in INVALID_MANUFACTURER_CHARACTERS
            or ord(character) < MINIMUM_PRINTABLE_CODEPOINT
            for character in response
        )
        if response and not response.endswith(".") and not has_invalid_character:
            return response
        logger.warning(
            "Enter a storage manufacturer using characters valid in a Windows folder name."
        )


def prompt_run_selection(
    supports_uasp: bool | None,
    input_func: Callable[[str], str] = input,
) -> RunSelection:
    # None is used when configuration is collected before DUT enumeration.
    # Offer UASP provisionally and resolve it once device capabilities are known.
    tests = TEST_OPTIONS + ((UASP_OPTION,) if supports_uasp is not False else ())
    selected_tests = _prompt_numbered("Test Selection", tests, input_func)
    selected_controllers = _prompt_numbered(
        "Controller Selection",
        CONTROLLER_OPTIONS,
        input_func,
    )
    selected_protocols = _prompt_numbered(
        "USB Protocol Selection",
        PROTOCOL_OPTIONS,
        input_func,
    )
    storage_manufacturer = _prompt_storage_manufacturer(input_func)
    return RunSelection(
        tests=selected_tests,
        controllers=selected_controllers,
        protocols=selected_protocols,
        storage_manufacturer=storage_manufacturer,
    )


def resolve_device_capabilities(selection: RunSelection, supports_uasp: bool) -> RunSelection:
    """Remove provisional selections unsupported by the enumerated DUT."""
    if supports_uasp or "uasp" not in selection.tests:
        return selection
    logger.info("Skipping UASP Tests because the selected DUT does not support UASP.")
    return RunSelection(
        tests=tuple(test for test in selection.tests if test != "uasp"),
        controllers=selection.controllers,
        protocols=selection.protocols,
        storage_manufacturer=selection.storage_manufacturer,
    )


def ordered_controllers(selected: Iterable[str], current_controller: str) -> tuple[str, ...]:
    selected = set(selected)
    order = [current_controller] if current_controller in selected else []
    order.extend(
        controller
        for controller in ("ASMedia", "Intel")
        if controller in selected and controller != current_controller
    )
    return tuple(order)


def ordered_protocols(selected: Iterable[int]) -> tuple[int, ...]:
    selected = set(selected)
    return tuple(protocol for protocol in (USB3_PROTOCOL, USB2_PROTOCOL) if protocol in selected)
