"""Authentication step definitions."""
from __future__ import annotations

from behave import given, when, then  # type: ignore[import-not-found]

_users: dict[str, str] = {}
_session: dict = {}


@given('a user "{username}" with password "{password}"')
def step_create_user(context, username, password):
    _users[username] = password


@when('the user logs in with "{username}" and "{password}"')
def step_login(context, username, password):
    if _users.get(username) == password:
        _session["user"] = username
        _session["token"] = f"token-{username}-abc123"
        _session["error"] = None
    else:
        _session["user"] = None
        _session["token"] = None
        _session["error"] = "Invalid credentials"


@when('the user tries to register with "{username}" and "{password}"')
def step_register(context, username, password):
    if len(password) < 8:
        _session["error"] = "Password must be at least 8 characters"
        _session["registered"] = False
    else:
        _users[username] = password
        _session["registered"] = True
        _session["error"] = None


@then("the user should be authenticated")
def step_check_auth(context):
    assert _session.get("user") is not None, "User was not authenticated"


@then("the user should not be authenticated")
def step_check_not_auth(context):
    assert _session.get("user") is None, "User was unexpectedly authenticated"


@then("the session token should not be empty")
def step_check_token(context):
    assert _session.get("token"), "Session token is empty"


@then('the error message should be "{message}"')
def step_check_error_msg(context, message):
    assert _session.get("error") == message, (
        f"Expected error '{message}', got '{_session.get('error')}'"
    )


@then("registration should fail")
def step_check_registration_failed(context):
    assert not _session.get("registered"), "Registration unexpectedly succeeded"
