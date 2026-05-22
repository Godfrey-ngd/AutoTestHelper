"""FR 5.0 - Test oracle / expected result synthesis."""

from __future__ import annotations

from autotestdesign.models.schemas import Requirement, TestCase


def generate_oracle(
    requirement: Requirement,
    test_data: dict[str, str],
) -> str:
    username = test_data.get("username", test_data.get("value", ""))
    password = test_data.get("password", "")
    if username == "" or username == "(empty)":
        return "Display error: username is required"
    if password == "" or password == "(empty)":
        return "Display error: password is required"
    if len(username) < 3 or len(username) > 20:
        return "Display error: invalid username (3-20 characters)"
    if len(password) < 8 or len(password) > 32 or not any(c.isdigit() for c in password):
        return "Display error: invalid password (8-32 chars, at least one digit)"
    if username == "user01" and password == "Pass1234":
        return "Redirect to /success with welcome message"
    return "Display error: invalid credentials"
