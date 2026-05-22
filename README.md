# Assignment 2 — AutoTestDesign

## What is what?

| Component | Role |
|-----------|------|
| **AutoTestDesign** (`autotestdesign/`) | AI-driven **test design** tool you build (FR 1.0–3.0, 6.0 + interactive review) |
| **Target app** (`target-app/`) | **System under test** — simple login Web module |
| **Target app tests** (`target-app-tests/`) | Playwright scripts that **execute** tests on the login module |
| **docs/** | Report drafts (risk analysis, test plan, detailed design) for the **target app** |

## Quick start

```bash
cd Assignment2
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
copy .env.example .env     # optional: set OPENAI_API_KEY
```

### Run AutoTestDesign UI

```bash
streamlit run autotestdesign/ui/streamlit_app.py
```

Without `OPENAI_API_KEY`, the tool uses **rule-based fallback** generators (sufficient for demo and offline use).

### Run target login app

```bash
python target-app/app.py
```

Open http://127.0.0.1:5000

### Run automated tests (target app)

```bash
pytest target-app-tests/test_login_client.py autotestdesign/tests -v
```

Optional Playwright E2E (after `pip install playwright` and `playwright install chromium`):

```bash
pytest target-app-tests/test_login.py -v
```

### Optional REST API

```bash
uvicorn autotestdesign.app.main:app --reload --port 8000
```

## Functional requirements implemented

| FR | Module |
|----|--------|
| 1.0 | `core/importers/` |
| 1.1 | `core/parser/` + `prompts/structure_requirement.md` |
| 2.0 | `core/risk/` + `prompts/risk_assessment.md` |
| 3.0 | `core/techniques/` (EP, BVA, Decision Table) |
| 4.0 | `core/whitebox/` (optional) |
| 5.0 | `core/oracle/` (optional) |
| 6.0 | `core/exporters/` |
| 7.0 | `core/optimizer/` (optional) |

## Interactive review

Streamlit tabs: Coverage, Strategy, Test Cases, Traceability, Improvement — all support **edit + save** with `ReviewEvent` audit log.

## Performance (NFR)

Run benchmark:

```bash
python scripts/benchmark_pipeline.py
```

Target: case generation &lt; 2s with cached/rule-based path. Document results in README if using LLM (typically slower).

## Submission zip contents

- `autotestdesign/` (source + `prompts/`)
- `target-app/`, `target-app-tests/`
- `README.md`, `requirements.txt`, `.env.example`
- Demo video (record Streamlit + 2–3 Playwright tests)

## Team

Edit cover pages in `docs/` with Team ID, names, and student IDs before PDF export.
