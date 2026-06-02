"""TestRunner: reads exported test cases and executes them against a SUT.

Supports two modes:
- client: imports the Flask app directly, uses test_client (no server needed)
- http: sends HTTP requests to a running server via the requests library
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests

from .assertions import BUILTIN


@dataclass
class TestResult:
    test_id: str
    title: str
    passed: bool
    expected: str
    actual: str
    technique: str
    requirement_id: str
    error: str | None = None


@dataclass
class TestReport:
    results: list[TestResult] = field(default_factory=list)

    @property
    def summary(self) -> dict:
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = total - passed
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": f"{passed / total * 100:.1f}%" if total > 0 else "N/A",
        }

    def to_console(self) -> str:
        lines = [
            "=" * 70,
            "  Test Execution Report",
            "=" * 70,
        ]
        for r in self.results:
            status = "PASS" if r.passed else "FAIL"
            lines.append(f"  [{status}] {r.test_id}  {r.title}")
            if not r.passed:
                lines.append(f"         Expected: {r.expected[:100]}")
                lines.append(f"         Actual:   {r.actual[:100]}")
            if r.error:
                lines.append(f"         Error: {r.error}")
        lines.append("-" * 70)
        s = self.summary
        lines.append(
            f"  Total: {s['total']}  |  Passed: {s['passed']}  |  "
            f"Failed: {s['failed']}  |  Rate: {s['pass_rate']}"
        )
        lines.append("=" * 70)
        return "\n".join(lines)

    def to_json(self, path: str | Path) -> None:
        data = {
            "summary": self.summary,
            "results": [
                {
                    "id": r.test_id,
                    "title": r.title,
                    "passed": r.passed,
                    "expected": r.expected,
                    "actual": r.actual,
                    "technique": r.technique,
                    "requirement_id": r.requirement_id,
                    "error": r.error,
                }
                for r in self.results
            ],
        }
        Path(path).write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )


class TestRunner:
    """Execute exported test cases against a SUT defined by a mapping config."""

    def __init__(
        self,
        project_path: str | Path,
        mapping_path: str | Path,
        mode: str = "client",
        base_url: str | None = None,
        filter_tag: str | None = None,
        filter_suite: str | None = None,
        filter_tech: str | None = None,
    ):
        self.project_path = Path(project_path)
        self.mapping = json.loads(Path(mapping_path).read_text(encoding="utf-8"))
        self.mode = mode
        self.base_url = base_url or self.mapping.get("base_url", "http://127.0.0.1:5000")
        self._repo_root = Path(__file__).resolve().parents[1]
        self._filter_tag = filter_tag
        self._filter_suite = filter_suite
        self._filter_tech = filter_tech

        self._load_project()
        self._apply_filters()
        self._setup_client()
        self._compile_rules()

    # ------------------------------------------------------------------
    # setup
    # ------------------------------------------------------------------

    def _load_project(self) -> None:
        data = json.loads(self.project_path.read_text(encoding="utf-8"))
        self.test_cases = data.get("test_cases", [])
        self.requirements = {r["id"]: r for r in data.get("requirements", [])}

    def _apply_filters(self) -> None:
        """Filter test_cases by tag, suite_id, or technique before execution."""
        before = len(self.test_cases)
        if self._filter_tag:
            tag = self._filter_tag
            self.test_cases = [
                tc for tc in self.test_cases
                if tag in (tc.get("tags") or [])
            ]
        if self._filter_suite:
            sid = self._filter_suite
            self.test_cases = [
                tc for tc in self.test_cases
                if tc.get("suite_id") == sid
            ]
        if self._filter_tech:
            tech = self._filter_tech
            self.test_cases = [
                tc for tc in self.test_cases
                if tc.get("technique", "").upper() == tech.upper()
            ]
        after = len(self.test_cases)
        if before != after:
            print(f"[filter] {before} → {after} test cases")

    def _setup_client(self) -> None:
        self._flask_app = None
        self._flask_client = None
        if self.mode != "client":
            return

        module_path: str = self.mapping["sut"]["module"]
        app_var: str = self.mapping["sut"]["app_var"]

        module_file = self._repo_root / f"{module_path.replace('.', '/')}.py"
        spec = importlib.util.spec_from_file_location("_sut_module", module_file)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["_sut_module"] = mod
        spec.loader.exec_module(mod)

        self._flask_app = getattr(mod, app_var)
        self._flask_app.config["TESTING"] = True
        self._flask_client = self._flask_app.test_client()

    def _compile_rules(self) -> None:
        self._rules: list[dict] = []
        for rule in self.mapping.get("assertion_rules", []):
            self._rules.append(
                {
                    "pattern": re.compile(rule["match"], re.IGNORECASE),
                    "use": rule["use"],
                    "repeat": rule.get("repeat", 1),
                }
            )
        self._default_assertion: str = self.mapping.get(
            "default_assertion", "text_contains_fuzzy"
        )

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def run(self) -> TestReport:
        report = TestReport()
        for tc in self.test_cases:
            self._reset_sut()
            result = self._run_one(tc)
            report.results.append(result)
        return report

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    def _reset_sut(self) -> None:
        endpoint = self.mapping.get("reset_endpoint", "/reset")
        if self._flask_client:
            self._flask_client.get(endpoint)
        else:
            try:
                requests.get(f"{self.base_url}{endpoint}", timeout=5)
            except requests.ConnectionError:
                pass

    def _run_one(self, tc: dict) -> TestResult:
        test_id = tc.get("id", "?")
        title = tc.get("title", "")
        expected = tc.get("expected", "")
        technique = tc.get("technique", "")
        req_id = tc.get("requirement_id", "")
        test_data = self._normalize_test_data(tc.get("test_data", {}))

        try:
            endpoint_name = self.mapping.get("default_endpoint", "login")
            endpoint = self.mapping["endpoints"][endpoint_name]

            # build request params, use defaults only for missing keys
            defaults = self.mapping.get("params_defaults", {})
            params = {}
            for k in endpoint.get("params", []):
                if k in test_data:
                    params[k] = test_data[k]  # keep empty string as-is
                else:
                    params[k] = defaults.get(k, "")

            # determine assertion & repeat count
            assertion_name = self._default_assertion
            repeat = 1
            for rule in self._rules:
                if rule["pattern"].search(expected):
                    assertion_name = rule["use"]
                    repeat = rule["repeat"]
                    break

            # execute (repeat for stateful scenarios like lockout)
            response = None
            for _ in range(repeat):
                response = self._execute(
                    endpoint["method"], endpoint["path"], params
                )

            assert_fn = BUILTIN.get(assertion_name, BUILTIN["text_contains"])
            passed = assert_fn(response, expected)
            actual = _extract_actual(response)

            return TestResult(
                test_id=test_id,
                title=title,
                passed=passed,
                expected=expected,
                actual=actual,
                technique=technique,
                requirement_id=req_id,
            )
        except Exception as exc:
            return TestResult(
                test_id=test_id,
                title=title,
                passed=False,
                expected=expected,
                actual="",
                technique=technique,
                requirement_id=req_id,
                error=f"{type(exc).__name__}: {exc}",
            )

    def _normalize_test_data(self, test_data: object) -> dict:
        if isinstance(test_data, dict):
            return test_data
        if isinstance(test_data, str):
            try:
                parsed = json.loads(test_data)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass
        return {}

    def _execute(self, method: str, path: str, params: dict) -> Any:
        if self._flask_client:
            fn = getattr(self._flask_client, method.lower())
            return fn(path, data=params, follow_redirects=False)

        url = f"{self.base_url}{path}"
        fn = getattr(requests, method.lower())
        return fn(url, data=params, allow_redirects=False, timeout=10)


# ------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------

def _extract_actual(response: Any) -> str:
    """Extract a human-readable summary from an HTTP response."""
    status = getattr(response, "status_code", 0)

    if status == 302:
        location = response.headers.get("Location", "")
        return f"[302 → {location}]"

    if hasattr(response, "text"):
        text = response.text
    elif hasattr(response, "data"):
        data = response.data
        text = data.decode("utf-8") if isinstance(data, bytes) else data
    else:
        text = str(response)

    # try to show the most relevant part
    for tag in ("error-msg", "lock-msg", "welcome"):
        import re as _re

        m = _re.search(rf'<[^>]+id="{tag}"[^>]*>(.*?)</', text, _re.DOTALL)
        if m:
            return m.group(1).strip()[:200]

    if len(text) > 200:
        return text[:200] + "..."
    return text
