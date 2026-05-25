"""Built-in assertion functions for TestRunner.

Each function takes (response, expected: str) and returns bool.
"""

from __future__ import annotations

import re
from typing import Any


def _get_text(response: Any) -> str:
    """Extract response body text (works with Flask test client and requests)."""
    if hasattr(response, "text"):
        return response.text
    if hasattr(response, "data"):
        data = response.data
        return data.decode("utf-8") if isinstance(data, bytes) else data
    return str(response)


def _extract_quoted(text: str) -> list[str]:
    """Extract single-quoted or backtick-quoted substrings from expected text.

    LLM-generated expected often wraps SUT messages in quotes, e.g.:
    "Error message 'username is required' displayed" → ["username is required"]
    """
    quoted = re.findall(r"['\"`]([^'\"`]{2,})['\"`]", text)
    return [q.strip() for q in quoted if q.strip()]


def _split_chunks(text: str, min_len: int = 4) -> list[str]:
    """Split text by common delimiters into candidate chunks."""
    parts = re.split(r"[.;,()\n]+", text)
    return [p.strip() for p in parts if len(p.strip()) >= min_len]


def text_contains_fuzzy(response: Any, expected: str) -> bool:
    """Check if response body contains expected text, with fuzzy fallback.

    Strategy (tried in order):
    1. Exact match: expected in response
    2. Quoted substrings: any '...' from expected found in response
    3. Chunk match: any sentence/phrase from expected found in response
    4. Behavioral: if expected suggests rejection → response shows error;
       if expected suggests acceptance → response is success/redirect
    """
    response_text = _get_text(response).lower()
    expected_lower = expected.lower()

    # 1. Exact match
    if expected_lower in response_text:
        return True

    # 2. Quoted substrings (LLM wraps SUT messages in quotes)
    for q in _extract_quoted(expected):
        if q.lower() in response_text:
            return True

    # 3. Chunk match — any meaningful segment
    for chunk in _split_chunks(expected):
        if chunk.lower() in response_text:
            return True

    # 4. Behavioral match — is the response error/success as expected?
    status = getattr(response, "status_code", 0)
    is_success = status == 302 or (
        status == 200 and _has_success_indicator(response_text)
    )
    is_error = not is_success and _has_error_indicator(response_text)

    if _expects_rejection(expected_lower):
        return is_error
    if _expects_acceptance(expected_lower):
        return is_success

    return False


def _has_error_indicator(text: str) -> bool:
    return bool(re.search(r"(error|invalid|required|locked|denied|blocked)", text))


def _has_success_indicator(text: str) -> bool:
    # Only match success-indicating CONTENT, not CSS/HTML attributes
    # "Welcome" and "Logout" are the unique text on the success page
    return bool(re.search(r"\b(welcome|logout)\b", text))


def _expects_rejection(expected: str) -> bool:
    return bool(
        re.search(r"\b(rejected|error|invalid|blocked|denied|required|locked)\b", expected)
    )


def _expects_acceptance(expected: str) -> bool:
    return bool(
        re.search(r"\b(accepted|valid|success|passed|redirect|welcome)\b", expected)
    )


def text_contains(response: Any, expected: str) -> bool:
    """Check if response body contains expected text (case-insensitive)."""
    return expected.lower() in _get_text(response).lower()


def redirect_or_text(response: Any, expected: str) -> bool:
    """Check if response is a redirect (302), else fall back to fuzzy text match."""
    if getattr(response, "status_code", None) == 302:
        return True
    return text_contains_fuzzy(response, expected)


BUILTIN: dict[str, Any] = {
    "text_contains": text_contains,
    "text_contains_fuzzy": text_contains_fuzzy,
    "redirect_or_text": redirect_or_text,
}
