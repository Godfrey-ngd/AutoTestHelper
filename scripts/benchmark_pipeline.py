"""Measure pipeline performance for NFR documentation."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from autotestdesign.core.pipeline import import_requirements, run_full_pipeline
from autotestdesign.models.schemas import Project

SAMPLE = Path(ROOT / "sample_data" / "login_requirements.csv").read_text(encoding="utf-8")


def main() -> None:
    runs = []
    for i in range(5):
        p = Project(name=f"bench-{i}")
        p = import_requirements(p, SAMPLE, "csv")
        t0 = time.perf_counter()
        p, metrics = run_full_pipeline(p)
        elapsed = (time.perf_counter() - t0) * 1000
        runs.append(elapsed)
        print(
            f"Run {i+1}: total={elapsed:.1f}ms "
            f"(structure={metrics.structure_ms:.1f}, "
            f"risk={metrics.risk_ms:.1f}, "
            f"techniques={metrics.techniques_ms:.1f}) "
            f"cases={len(p.test_cases)}"
        )
    avg = sum(runs) / len(runs)
    p95 = sorted(runs)[int(len(runs) * 0.95)]
    print(f"\nAverage: {avg:.1f} ms | P95: {p95:.1f} ms | Target: 2000 ms")
    if p95 <= 2000:
        print("PASS: P95 within 2s (rule-based / cached path)")
    else:
        print("NOTE: Exceeds 2s — document LLM latency or enable caching in report")


if __name__ == "__main__":
    main()
