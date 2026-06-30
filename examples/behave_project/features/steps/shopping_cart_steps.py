"""Shopping cart step definitions."""
from __future__ import annotations

from behave import given, when, then  # type: ignore[import-not-found]

_cart: dict = {}


@given("an empty shopping cart")
def step_empty_cart(context):
    _cart.clear()
    _cart["items"] = []
    _cart["total"] = 0.0


@given('I add "{item}" priced at ${price:d} to the cart')
def step_given_add_item(context, item, price):
    _cart["items"].append({"name": item, "price": price})
    _cart["total"] = sum(i["price"] for i in _cart["items"])


@when('I add "{item}" priced at ${price:d} to the cart')
def step_add_item(context, item, price):
    _cart["items"].append({"name": item, "price": price})
    _cart["total"] = sum(i["price"] for i in _cart["items"])


@when('I remove "{item}" from the cart')
def step_remove_item(context, item):
    _cart["items"] = [i for i in _cart["items"] if i["name"] != item]
    _cart["total"] = sum(i["price"] for i in _cart["items"])


@when('I apply the discount code "{code}"')
def step_apply_discount(context, code):
    discounts = {"SAVE10": 0.10, "SAVE20": 0.20, "HALF": 0.50}
    rate = discounts.get(code, 0.0)
    _cart["total"] = round(_cart["total"] * (1 - rate), 2)


@then("the cart should contain {count:d} items")
def step_check_cart_count(context, count):
    actual = len(_cart["items"])
    assert actual == count, f"Expected {count} items, got {actual}"


@then("the cart total should be ${total:d}")
def step_check_cart_total(context, total):
    actual = _cart["total"]
    assert actual == total, f"Expected ${total}, got ${actual}"
