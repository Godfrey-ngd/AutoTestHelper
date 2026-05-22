"""Pytest fixtures for target-app-tests."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def flask_server():
    """Start target-app Flask server for Playwright E2E tests."""
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "target-app" / "app.py")],
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(1.5)
    yield proc
    proc.terminate()
    proc.wait(timeout=5)


@pytest.fixture(autouse=True)
def _playwright_reset(request):
    """Reset lock state before each Playwright E2E test (test_login.py only)."""
    if "page" not in request.fixturenames:
        return
    base = os.getenv("TARGET_APP_URL", "http://127.0.0.1:5000")
    page = request.getfixturevalue("page")
    page.goto(f"{base}/reset")
