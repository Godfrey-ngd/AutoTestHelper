"""CLI entry point for test runner.

Usage:
  python -m test_runner exports/project.json -m test_runner/mappings/login.json
  python -m test_runner exports/project.json -m ... --mode http --base-url http://127.0.0.1:5000
"""

from __future__ import annotations

import argparse
import sys

from .runner import TestRunner


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run exported test cases against a SUT"
    )
    parser.add_argument(
        "project", help="Path to exported project JSON file"
    )
    parser.add_argument(
        "--mapping", "-m", required=True, help="Path to SUT mapping config JSON"
    )
    parser.add_argument(
        "--mode",
        choices=["client", "http"],
        default="client",
        help="Execution mode: client (Flask test client) or http (running server)",
    )
    parser.add_argument(
        "--base-url",
        help="SUT base URL (only used in http mode, defaults to mapping config value)",
    )
    parser.add_argument(
        "--output", "-o", help="Save JSON report to file"
    )
    args = parser.parse_args()

    runner = TestRunner(
        args.project,
        args.mapping,
        mode=args.mode,
        base_url=args.base_url,
    )
    report = runner.run()
    print(report.to_console())

    if args.output:
        report.to_json(args.output)
        print(f"\nReport saved to {args.output}")

    if report.summary["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
