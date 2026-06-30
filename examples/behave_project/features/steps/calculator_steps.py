"""Calculator step definitions."""
from __future__ import annotations

from behave import given, when, then  # type: ignore[import-not-found]

_calculator: dict = {}


@given("a calculator is turned on")
def step_calculator_on(context):
    _calculator.clear()
    _calculator["display"] = "0"
    _calculator["error"] = None


@given("I have entered {number:d} into the calculator")
def step_enter_number(context, number):
    _calculator.setdefault("entries", []).append(number)


@when("I press add")
def step_press_add(context):
    entries = _calculator.get("entries", [])
    _calculator["display"] = str(sum(entries))


@when("I press subtract")
def step_press_subtract(context):
    entries = _calculator.get("entries", [])
    result = entries[0]
    for n in entries[1:]:
        result -= n
    _calculator["display"] = str(result)


@when("I press multiply")
def step_press_multiply(context):
    entries = _calculator.get("entries", [])
    result = 1
    for n in entries:
        result *= n
    _calculator["display"] = str(result)


@when("I press divide")
def step_press_divide(context):
    entries = _calculator.get("entries", [])
    if entries[1] == 0:
        _calculator["error"] = "Cannot divide by zero"
        _calculator["display"] = "Error"
    else:
        _calculator["display"] = str(entries[0] / entries[1])


@then("the result should be {expected:d} on the screen")
def step_check_result(context, expected):
    display = _calculator["display"]
    if "." in display:
        result = float(display)
    else:
        result = int(display)
    assert result == expected, (
        f"Expected {expected}, got {_calculator['display']}"
    )


@then('the calculator should show "{message}"')
def step_check_error(context, message):
    assert _calculator.get("error") == message, (
        f"Expected error '{message}', got '{_calculator.get('error')}'"
    )
