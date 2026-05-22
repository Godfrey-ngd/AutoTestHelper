"""Playwright E2E tests (optional — requires: pip install playwright && playwright install chromium)."""

from __future__ import annotations

import pytest

pytest.importorskip("playwright")
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.usefixtures("flask_server")


def _login(page: Page, base_url: str, username: str, password: str) -> None:
    page.goto(base_url)
    page.fill("#username", username)
    page.fill("#password", password)
    page.click("#login-btn")


@pytest.mark.parametrize(
    "username,password,expected_substr",
    [
        ("", "Pass1234", "username is required"),
        ("user01", "", "password is required"),
        ("ab", "Pass1234", "invalid username"),
        ("user01", "short", "invalid password"),
        ("user01", "Password", "invalid password"),
        ("user01", "Wrong999", "invalid credentials"),
    ],
)
def test_login_validation_errors(
    page: Page, base_url: str, username: str, password: str, expected_substr: str
):
    _login(page, base_url, username, password)
    expect(page.locator("#error-msg").first).to_contain_text(expected_substr)


def test_valid_login_success(page: Page, base_url: str):
    _login(page, base_url, "user01", "Pass1234")
    expect(page).to_have_url(f"{base_url}/success")
    expect(page.locator("#welcome")).to_contain_text("Welcome")


def test_username_min_boundary_valid(page: Page, base_url: str):
    _login(page, base_url, "usr", "Pass1234")
    expect(page).to_have_url(f"{base_url}/success")


def test_username_max_boundary_valid(page: Page, base_url: str):
    name = "a" * 20
    _login(page, base_url, name, "Pass1234")
    expect(page.locator("#error-msg").first).to_contain_text("invalid credentials")


def test_username_below_min_invalid(page: Page, base_url: str):
    _login(page, base_url, "ab", "Pass1234")
    expect(page.locator("#error-msg").first).to_contain_text("invalid username")


def test_password_min_boundary_valid(page: Page, base_url: str):
    _login(page, base_url, "user01", "Pass1234")
    expect(page).to_have_url(f"{base_url}/success")


def test_account_lock_after_three_failures(page: Page, base_url: str):
    for _ in range(3):
        _login(page, base_url, "user01", "Wrong999")
    expect(page.locator("#lock-msg")).to_be_visible()
