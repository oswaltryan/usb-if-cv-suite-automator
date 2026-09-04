import re

from cv_suite_automator.run_config import (
    ordered_controllers,
    ordered_protocols,
    prompt_run_selection,
    resolve_device_capabilities,
)

INVALID_MANUFACTURER_RESPONSE_COUNT = 3
RUN_CONFIGURATION_PROMPT_COUNT = 4


def answers(*values):
    iterator = iter(values)
    return lambda _prompt: next(iterator)


def test_blank_answers_select_all_non_uasp_options() -> None:
    selection = prompt_run_selection(False, answers("", "", "", "Phison"))

    assert selection.tests == ("chapter9", "connector", "summary", "msc")
    assert selection.controllers == ("ASMedia", "Intel")
    assert selection.protocols == (2, 3)
    assert selection.storage_manufacturer == "Phison"
    assert selection.test_ids(2) == (1, 3, 6, 17)
    assert selection.test_ids(3) == (2, 3, 6, 17)


def test_space_separated_answers_are_deduplicated_in_display_order() -> None:
    selection = prompt_run_selection(True, answers("5 3 3 1", "2", "2 1", "Kioxia"))

    assert selection.tests == ("chapter9", "summary", "uasp")
    assert selection.controllers == ("Intel",)
    assert selection.protocols == (2, 3)


def test_invalid_answer_reprompts_only_current_question() -> None:
    selection = prompt_run_selection(False, answers("bad", "9", "2", "1", "2", "WD"))

    assert selection.tests == ("connector",)
    assert selection.controllers == ("ASMedia",)
    assert selection.protocols == (3,)


def test_execution_order_starts_with_current_controller_and_usb3() -> None:
    assert ordered_controllers(("ASMedia", "Intel"), "Intel") == ("Intel", "ASMedia")
    assert ordered_controllers(("Intel",), "ASMedia") == ("Intel",)
    assert ordered_protocols((2, 3)) == (3, 2)


def test_pre_enumeration_selection_offers_uasp_provisionally() -> None:
    responses = iter(("5", "", "", "SMI"))

    selection = prompt_run_selection(None, lambda _: next(responses))

    assert selection.tests == ("uasp",)


def test_unsupported_uasp_selection_is_removed_after_enumeration() -> None:
    responses = iter(("", "1", "1", "Phison"))
    selection = prompt_run_selection(None, lambda _: next(responses))

    resolved = resolve_device_capabilities(selection, supports_uasp=False)

    assert resolved.tests == ("chapter9", "connector", "summary", "msc")
    assert resolved.storage_manufacturer == "Phison"


def test_manufacturer_is_normalized_after_protocol_selection() -> None:
    prompts = []

    def capture(prompt):
        prompts.append(prompt)
        return "  Western\t  Digital  " if "Storage Manufacturer" in prompt else ""

    selection = prompt_run_selection(False, capture)

    assert selection.storage_manufacturer == "Western Digital"
    assert prompts[-1].endswith("Storage Manufacturer: ")


def test_invalid_manufacturer_reprompts_only_manufacturer(caplog) -> None:
    selection = prompt_run_selection(
        False,
        answers("1", "1", "1", "", "bad/name", "trailing.", "Micron"),
    )

    assert selection.tests == ("chapter9",)
    assert selection.controllers == ("ASMedia",)
    assert selection.protocols == (2,)
    assert selection.storage_manufacturer == "Micron"
    assert (
        caplog.text.count("valid in a Windows folder name") == INVALID_MANUFACTURER_RESPONSE_COUNT
    )


def test_input_prompts_include_timestamp() -> None:
    prompts = []

    def capture(prompt):
        prompts.append(prompt)
        return "Phison" if "Storage Manufacturer" in prompt else ""

    prompt_run_selection(False, capture)

    assert len(prompts) == RUN_CONFIGURATION_PROMPT_COUNT
    assert all(
        re.fullmatch(
            r"\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\] Selection: ",
            prompt,
        )
        for prompt in prompts[:3]
    )
    assert re.fullmatch(
        r"\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\] Storage Manufacturer: ",
        prompts[3],
    )
