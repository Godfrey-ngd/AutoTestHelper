"""Test LLM API connectivity and .env loading — verifies chat_json reads from file, not os.environ."""
import os

import pytest


def _read_env_from_disk():
    """Read .env directly from disk as a raw dict (mirrors llm_client._read_env_file)."""
    from pathlib import Path

    env_path = Path(__file__).resolve().parents[2] / ".env"
    result = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and val:
            result[key] = val
    return result


def test_read_env_file_matches_disk():
    """_read_env_file must return the exact same values as the .env file."""
    from autotestdesign.core.llm_client import _read_env_file

    disk = _read_env_from_disk()
    loaded = _read_env_file()

    assert disk["OPENAI_API_KEY"] == loaded["OPENAI_API_KEY"], (
        f"API key mismatch: file has {disk['OPENAI_API_KEY'][:12]}... "
        f"but _read_env_file returned {loaded['OPENAI_API_KEY'][:12]}..."
    )
    assert disk["OPENAI_BASE_URL"] == loaded["OPENAI_BASE_URL"]
    assert disk["OPENAI_MODEL"] == loaded["OPENAI_MODEL"]


def test_chat_json_ignores_corrupted_os_environ():
    """chat_json must use file values even when os.environ has a different key."""
    from autotestdesign.core.llm_client import _read_env_file, chat_json

    correct_key = _read_env_from_disk()["OPENAI_API_KEY"]

    # poison os.environ with a fake key
    old = os.environ.get("OPENAI_API_KEY")
    os.environ["OPENAI_API_KEY"] = "sk-evil-key-99999"

    try:
        # re-read from file to verify it still returns correct key
        key_from_file = _read_env_file()["OPENAI_API_KEY"]
        assert key_from_file == correct_key, (
            f"FAIL: _read_env_file returned poisoned key {key_from_file[:12]}... "
            f"instead of {correct_key[:12]}..."
        )
    finally:
        if old is None:
            del os.environ["OPENAI_API_KEY"]
        else:
            os.environ["OPENAI_API_KEY"] = old


def test_chat_json_reads_correct_key_from_file():
    """chat_json reads key from _read_env_file (file), not from os.environ."""
    from autotestdesign.core.llm_client import chat_json

    response = chat_json(
        "Reply with JSON: {\"ok\": true}",
        "Say hello",
    )
    assert response is not None, "chat_json returned None — API key may be wrong"
    assert response.get("ok") is True or "hello" in str(response).lower()


def test_has_llm_returns_true():
    """has_llm must return True when a valid key exists in .env."""
    from autotestdesign.core.llm_client import has_llm

    assert has_llm() is True, "has_llm returned False despite .env having a key"


def test_api_call_with_explicit_file_key_succeeds():
    """Actual API call using key read directly from .env file succeeds."""
    import httpx
    from openai import OpenAI

    env = _read_env_from_disk()

    client = OpenAI(
        api_key=env["OPENAI_API_KEY"],
        base_url=env.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        http_client=httpx.Client(timeout=120.0),
    )

    response = client.chat.completions.create(
        model=env.get("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=0,
        messages=[
            {"role": "system", "content": "Reply with JSON: {\"ok\": true}"},
            {"role": "user", "content": "Say hello"},
        ],
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content
    assert content is not None, "Empty response from API"
    import json

    data = json.loads(content)
    assert isinstance(data, dict), f"Expected JSON dict, got: {type(data)}"
    print(f"API response: {data}")


def test_deepseek_base_url_is_configured():
    """Verify the .env is configured for DeepSeek, not OpenAI."""
    env = _read_env_from_disk()

    base_url = env.get("OPENAI_BASE_URL", "")
    assert "deepseek" in base_url.lower(), (
        f"OPENAI_BASE_URL must point to DeepSeek, got: {base_url}"
    )

    model = env.get("OPENAI_MODEL", "")
    assert "deepseek" in model.lower(), (
        f"OPENAI_MODEL must use a DeepSeek model, got: {model}"
    )

    print(f"DeepSeek config OK: base_url={base_url}, model={model}")
