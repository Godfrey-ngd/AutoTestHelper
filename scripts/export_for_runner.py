"""Export project from full pipeline for Test Runner validation."""
from pathlib import Path
from autotestdesign.models.schemas import Project
from autotestdesign.core.pipeline import run_full_pipeline, import_requirements
from autotestdesign.core.exporters import export_json_bytes

# 1. Create project & import login requirements
project = Project(name="Login Module Test")
reqs_csv = Path("sample_data/login_requirements.csv").read_text(encoding="utf-8")
project = import_requirements(project, reqs_csv, source="csv")
print(f"Imported {len(project.requirements)} requirements")

# 2. Run full pipeline with LLM
project, metrics = run_full_pipeline(project)
print(f"Pipeline done: structure={metrics.structure_ms:.0f}ms, "
      f"risk={metrics.risk_ms:.0f}ms, techniques={metrics.techniques_ms:.0f}ms")
print(f"Generated {len(project.test_cases)} test cases")

# 3. Export
output = Path("exports/login_project.json")
output.parent.mkdir(exist_ok=True)
output.write_bytes(export_json_bytes(project))
print(f"Exported to {output}")

# 4. Show sample test cases
for tc in project.test_cases[:5]:
    print(f"\n{tc.id} | {tc.title} | technique={tc.technique}")
    print(f"  test_data: {tc.test_data}")
    print(f"  expected: {tc.expected}")
