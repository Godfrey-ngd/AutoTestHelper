# Assignment 2 — AutoTestDesign

## What is what?

| Component | Role |
|-----------|------|
| **AutoTestDesign** (`autotestdesign/`) | AI-driven **test design** tool you build (FR 1.0–3.0, 6.0 + interactive review) |
| **Target app** (`target-app/`) | **System under test** — simple login Web module |
| **Target app tests** (`target-app-tests/`) | Playwright scripts that **execute** tests on the login module |
| **docs/** | Report drafts + **[用户使用手册](docs/用户使用手册.md)**（Import 填写说明与 Web 操作） |

## Quick start (Conda 推荐)

前置：已安装 [Anaconda](https://www.anaconda.com/) 或 Miniconda，并在终端能执行 `conda`。

### 1. 创建并激活环境（只需一次）

```powershell

# 方式 A：用 environment.yml（推荐）
conda env create -f environment.yml

# 若环境已存在，改为更新：
# conda env update -f environment.yml --prune

conda activate autotestdesign
```

也可双击 `setup_conda.bat` 自动执行 `conda env create`。

### 2. 配置 API（可选）

```powershell
copy .env.example .env
# 编辑 .env，填入 OPENAI_API_KEY（不填则使用规则引擎 fallback）
```

### 3. 运行工具 UI（终端 1）

```powershell
conda activate autotestdesign
streamlit run autotestdesign/ui/streamlit_app.py
```

浏览器打开提示的地址（通常 http://localhost:8501）。侧边栏 **Create project** → 选 **Sample login requirements** → **Run full pipeline**。

### 4. 运行被测登录应用（终端 2）

```powershell
conda activate autotestdesign
python target-app/app.py
```

浏览器访问 http://127.0.0.1:5000

### 5. 运行自动化测试

```powershell
conda activate autotestdesign
pytest target-app-tests/test_login_client.py autotestdesign/tests -v
```

### 6. 性能基准（NFR）

```powershell
python scripts/benchmark_pipeline.py
```

### 7. 可选：REST API

```powershell
uvicorn autotestdesign.app.main:app --reload --port 8000
```

### 8. 可选：Playwright 浏览器 E2E

```powershell
pip install playwright pytest-playwright
playwright install chromium
pytest target-app-tests/test_login.py -v
```

（需先在一个终端运行 `python target-app/app.py`。）

### Conda 常用命令

| 操作 | 命令 |
|------|------|
| 激活环境 | `conda activate autotestdesign` |
| 退出环境 | `conda deactivate` |
| 删除环境 | `conda env remove -n autotestdesign` |
| 查看已装包 | `conda list` |

---

## Quick start (venv / pip 备选)

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
