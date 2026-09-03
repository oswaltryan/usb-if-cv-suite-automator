import re

from cv_suite_automator.run_config import (
    ordered_controllers,
    ordered_protocols,
    prompt_run_selection,
)


def answers(*values):
    iterator = iter(values)
    return lambda _prompt: next(iterator)


def test_blank_answers_select_all_non_uasp_options() -> None:
    selection = prompt_run_selection(False, answers("", "", ""))

    assert selection.tests == ("chapter9", "connector", "summary", "msc")
    assert selection.controllers == ("ASMedia", "Intel")
    assert selection.protocols == (2, 3)
    assert selection.test_ids(2) == (1, 3, 6, 17)
    assert selection.test_ids(3) == (2, 3, 6, 17)


def test_space_separated_answers_are_deduplicated_in_display_order() -> None:
    selection = prompt_run_selection(True, answers("5 3 3 1", "2", "2 1"))

    assert selection.tests == ("chapter9", "summary", "uasp")
    assert selection.controllers == ("Intel",)
    assert selection.protocols == (2, 3)


def test_invalid_answer_reprompts_only_current_question() -> None:
    selection = prompt_run_selection(False, answers("bad", "9", "2", "1", "2"))

    assert selection.tests == ("connector",)
    assert selection.controllers == ("ASMedia",)
    assert selection.protocols == (3,)


def test_execution_order_starts_with_current_controller_and_usb3() -> None:
    assert ordered_controllers(("ASMedia", "Intel"), "Intel") == ("Intel", "ASMedia")
    assert ordered_controllers(("Intel",), "ASMedia") == ("Intel",)
    assert ordered_protocols((2, 3)) == (3, 2)


def test_input_prompts_include_timestamp() -> None:
    prompts = []

    def capture(prompt):
        prompts.append(prompt)
        return ""

    prompt_run_selection(False, capture)

    assert len(prompts) == 3
    assert all(
        re.fullmatch(
            r"\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\] Selection: ",
            prompt,
        )
        for prompt in prompts
    )
