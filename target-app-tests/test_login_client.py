"""HTTP-level automated tests (no Playwright required)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_app():
    path = ROOT / "target-app" / "app.py"
    spec = importlib.util.spec_from_file_location("login_app", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["login_app"] = mod
    spec.loader.exec_module(mod)
    return mod.app


@pytest.fixture
def client():
    app = _load_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        c.get("/reset")
        yield c
        c.get("/reset")


def _post(client, username: str, password: str):
    return client.post(
        "/",
        data={"username": username, "password": password},
        follow_redirects=False,
    )


def test_empty_username(client):
    r = _post(client, "", "Pass1234")
    assert b"username is required" in r.data


def test_empty_password(client):
    r = _post(client, "user01", "")
    assert b"password is required" in r.data


def test_invalid_username_short(client):
    r = _post(client, "ab", "Pass1234")
    assert b"invalid username" in r.data


def test_invalid_password_short(client):
    r = _post(client, "user01", "short")
    assert b"invalid password" in r.data


def test_invalid_password_no_digit(client):
    r = _post(client, "user01", "Password")
    assert b"invalid password" in r.data


def test_invalid_credentials(client):
    r = _post(client, "user01", "Wrong999")
    assert b"invalid credentials" in r.data


def test_valid_login_redirect(client):
    r = _post(client, "user01", "Pass1234")
    assert r.status_code == 302
    assert "/success" in r.headers.get("Location", "")


def test_username_min_boundary_user(client):
    r = _post(client, "usr", "Pass1234")
    assert r.status_code == 302


def test_username_max_length_invalid_creds(client):
    r = _post(client, "a" * 20, "Pass1234")
    assert b"invalid credentials" in r.data


def test_account_lock_after_three_failures(client):
    for _ in range(3):
        _post(client, "user01", "Wrong999")
    r = client.get("/")
    assert b"Account locked" in r.data or b"locked" in r.data.lower()
