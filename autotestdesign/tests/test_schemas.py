"""Schema coercion tests for LLM-shaped payloads."""

from autotestdesign.models.schemas import TestCase, _coerce_test_data


def test_coerce_test_data_integers():
    raw = {"login_attempts": 3, "lock_seconds": 30, "active": True}
    out = _coerce_test_data(raw)
    assert out["login_attempts"] == "3"
    assert out["lock_seconds"] == "30"
    assert out["active"] == "true"


def test_build_case_from_llm_numeric_test_data():
    tc = TestCase(
        title="lock boundary",
        test_data={"login_attempts": 3},
        expected="locked",
    )
    assert tc.test_data["login_attempts"] == "3"
