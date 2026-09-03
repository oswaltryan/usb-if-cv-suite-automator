"""Interactive configuration for a CV Suite automation run."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Iterable, TypeVar

from .logging_config import timestamped_prompt


logger = logging.getLogger(__name__)
Choice = TypeVar("Choice")

TEST_OPTIONS = (
    ("chapter9", "Chapter 9 Tests"),
    ("connector", "Connector Type Tests"),
    ("summary", "Device Summary"),
    ("msc", "MSC Tests"),
)
UASP_OPTION = ("uasp", "UASP Tests")
CONTROLLER_OPTIONS = (("ASMedia", "ASMedia"), ("Intel", "Intel"))
PROTOCOL_OPTIONS = ((2, "USB2"), (3, "USB3"))


@dataclass(frozen=True)
class RunSelection:
    tests: tuple[str, ...]
    controllers: tuple[str, ...]
    protocols: tuple[int, ...]

    def test_ids(self, protocol: int) -> tuple[int, ...]:
        mapping = {
            "chapter9": 1 if protocol == 2 else 2,
            "connector": 3,
            "summary": 6,
            "msc": 17,
            "uasp": 21,
        }
        return tuple(mapping[test] for test in self.tests)


def _prompt_numbered(
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


def prompt_run_selection(
    supports_uasp: bool | None,
    input_func: Callable[[str], str] = input,
) -> RunSelection:
    # None is used when configuration is collected before DUT enumeration.
    # Offer UASP provisionally and resolve it once device capabilities are known.
    tests = TEST_OPTIONS + ((UASP_OPTION,) if supports_uasp is not False else ())
    return RunSelection(
        tests=_prompt_numbered("Test Selection", tests, input_func),
        controllers=_prompt_numbered("Controller Selection", CONTROLLER_OPTIONS, input_func),
        protocols=_prompt_numbered("USB Protocol Selection", PROTOCOL_OPTIONS, input_func),
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
    return tuple(protocol for protocol in (3, 2) if protocol in selected)
