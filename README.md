# Assignment 2 — AutoTestDesign

AI-driven test **design** tool (requirements → risk → black-box cases → review → export) plus a **login module** as the system under test (SUT) for assignment reports and automated tests.

---

## Documentation

| Document | Language | Contents |
|----------|----------|----------|
| **[docs/用户使用手册.md](docs/用户使用手册.md)** | 中文 | Streamlit UI, import formats, tabs, SUT, FAQ, demo flow |
| **[docs/project-templates.md](docs/project-templates.md)** | EN | 7 ready-made projects (name + target app + CSV requirements) |
| [docs/risk-analysis.md](docs/risk-analysis.md) | EN draft | Risk report (SUT) — fill team info, export PDF |
| [docs/test-plan.md](docs/test-plan.md) | EN draft | Test plan (SUT) |
| [docs/detailed-design-exec.md](docs/detailed-design-exec.md) | EN draft | Detailed design & execution (SUT) |
| [docs/performance-nfr.md](docs/performance-nfr.md) | EN | Performance notes (NFR) |

**New users:** install (below) → read **用户使用手册** §快速上手 → copy requirements from **project-templates** Template 1.

---

## Tool vs system under test

```text
┌─────────────────────────────┐     ┌──────────────────────────┐
│  AutoTestDesign (you build) │     │  target-app (SUT)        │
│  Streamlit :8501            │     │  Flask login :5000       │
│  Design cases, export CSV   │────▶│  Run manual / pytest     │
└─────────────────────────────┘     └──────────────────────────┘
```

| Path | Role |
|------|------|
| `autotestdesign/` | Tool source, `prompts/`, Streamlit UI |
| `target-app/` | Login SUT (username/password, lockout) |
| `target-app-tests/` | Automated tests against SUT |
| `sample_data/` | Example requirement CSV files |
| `data/projects/` | Saved projects (JSON, gitignored) |

---

## Install (Conda)

Requires [Anaconda](https://www.anaconda.com/) or Miniconda.

```powershell
cd C:\Users\86182\Desktop\Assignment2
conda env create -f environment.yml
conda activate autotestdesign
copy .env.example .env
```

Optional: set `OPENAI_API_KEY` in `.env` for LLM mode. If unset, the tool uses a **rule-based fallback** (offline, fast). See manual §LLM.

Update existing env: `conda env update -f environment.yml --prune`  
Windows shortcut: double-click `setup_conda.bat`.

### pip / venv (alternative)

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

---

## Command cheat sheet

All commands assume `conda activate autotestdesign` and project root.

| Goal | Command |
|------|---------|
| **Test design UI** | `streamlit run autotestdesign/ui/streamlit_app.py` → http://localhost:8501 |
| **Login SUT** | `python target-app/app.py` → http://127.0.0.1:5000 |
| **Automated tests** | `pytest target-app-tests/test_login_client.py autotestdesign/tests -v` |
| **Performance benchmark** | `python scripts/benchmark_pipeline.py` |
| **REST API (optional)** | `uvicorn autotestdesign.app.main:app --reload --port 8000` |
| **Playwright E2E (optional)** | Start SUT, then `pytest target-app-tests/test_login.py -v` |

Batch shortcuts: `run_ui.bat`, `run_target_app.bat`.

---

## Implemented requirements

| FR | Feature | Location |
|----|---------|----------|
| 1.0 | Import CSV / text / paste | `core/importers/` |
| 1.1 | Structure requirements | `core/parser/`, `prompts/structure_requirement.md` |
| 2.0 | Risk & priority H/M/L | `core/risk/` |
| 3.0 | EP, BVA, decision table | `core/techniques/` |
| 4.0 | State model (optional) | `core/whitebox/` |
| 5.0 | Test oracle (optional) | `core/oracle/` |
| 6.0 | Export JSON / CSV | `core/exporters/` |
| 7.0 | Suite optimization (optional) | `core/optimizer/` |
| — | Interactive review | Streamlit tabs + `ReviewEvent` |

---

