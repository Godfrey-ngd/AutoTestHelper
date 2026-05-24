# Assignment 2 — AutoTestDesign

AI 驱动的测试**用例设计**工具（需求 → 风险分析 → 黑盒用例 → 评审 → 导出），同时内置一个**登录模块**作为被测系统（SUT），用于作业报告和自动化测试。

---

## 文档

| 文档 | 语言 | 内容 |
|------|------|------|
| **[docs/用户使用手册.md](docs/用户使用手册.md)** | 中文 | Streamlit 界面、导入格式、功能页签、被测系统、常见问题、操作流程 |
| **[docs/project-templates.md](docs/project-templates.md)** | 英文 | 7 个现成的测试项目模板（名称 + 被测应用 + CSV 需求） |
| [docs/risk-analysis.md](docs/risk-analysis.md) | 英文草案 | 风险分析报告（SUT）— 填写团队信息，导出 PDF |
| [docs/test-plan.md](docs/test-plan.md) | 英文草案 | 测试计划（SUT） |
| [docs/detailed-design-exec.md](docs/detailed-design-exec.md) | 英文草案 | 详细设计与执行（SUT） |
| [docs/performance-nfr.md](docs/performance-nfr.md) | 英文 | 性能测试说明（NFR） |

**新用户上手路径：** 完成下方安装 → 阅读 **用户使用手册** 的 §快速上手 → 从 **project-templates** 模板 1 复制需求数据。

---

## 工具与被测系统的关系

```text
┌─────────────────────────────┐     ┌──────────────────────────┐
│  AutoTestDesign（测试设计工具）│     │  target-app（被测系统）    │
│  Streamlit :8501            │     │  Flask 登录 :5000        │
│  设计用例，导出 CSV          │────▶│  手动测试 / pytest 自动化  │
└─────────────────────────────┘     └──────────────────────────┘
```

| 目录 | 用途 |
|------|------|
| `autotestdesign/` | 工具源码、`prompts/` 提示词、Streamlit 界面 |
| `target-app/` | 登录被测系统（用户名/密码、锁定机制） |
| `target-app-tests/` | 针对被测系统的自动化测试 |
| `sample_data/` | 示例需求 CSV 文件 |
| `data/projects/` | 已保存的项目（JSON，已加入 .gitignore） |

---

## 安装（Conda）

需要安装 [Anaconda](https://www.anaconda.com/) 或 Miniconda。

```powershell
cd C:\Users\86182\Desktop\Assignment2
conda env create -f environment.yml
conda activate autotestdesign
copy .env.example .env
```

可选：在 `.env` 中配置 `OPENAI_API_KEY` 以启用 LLM 模式。未配置时，工具使用**基于规则的降级方案**（离线、快速）。详见用户手册 §LLM。

更新已有环境：`conda env update -f environment.yml --prune`  
Windows 快捷方式：双击 `setup_conda.bat`。

### pip / venv（备选方案）

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

---

## 命令速查表

以下命令均需先执行 `conda activate autotestdesign`，并在项目根目录下运行。

| 用途 | 命令 |
|------|------|
| **测试设计界面** | `streamlit run autotestdesign/ui/streamlit_app.py` → http://localhost:8501 |
| **启动登录被测系统** | `python target-app/app.py` → http://127.0.0.1:5000 |
| **运行自动化测试** | `pytest target-app-tests/test_login_client.py autotestdesign/tests -v` |
| **性能基准测试** | `python scripts/benchmark_pipeline.py` |
| **REST API（可选）** | `uvicorn autotestdesign.app.main:app --reload --port 8000` |
| **Playwright E2E（可选）** | 先启动被测系统，再执行 `pytest target-app-tests/test_login.py -v` |

批处理快捷方式：`run_ui.bat`、`run_target_app.bat`。

---

## 已实现的功能

| 功能编号 | 功能 | 代码位置 |
|----------|------|----------|
| 1.0 | 导入 CSV / 文本 / 粘贴 | `core/importers/` |
| 1.1 | 需求结构化 | `core/parser/`、`prompts/structure_requirement.md` |
| 2.0 | 风险等级与优先级 H/M/L | `core/risk/` |
| 3.0 | 等价类划分、边界值分析、判定表 | `core/techniques/` |
| 4.0 | 状态模型（可选） | `core/whitebox/` |
| 5.0 | 测试预言（可选） | `core/oracle/` |
| 6.0 | 导出 JSON / CSV | `core/exporters/` |
| 7.0 | 用例集优化（可选） | `core/optimizer/` |
| — | 交互式评审 | Streamlit 页签 + `ReviewEvent` |

---

