# Detailed Test Design & Execution — Login Module

**Team ID:** [填写]  
**Module under test:** Login (`target-app/app.py`)

---

## 1. Concept & coverage items

**Concept:** Secure login with field validation and lockout.  

**Coverage items (from AutoTestDesign):**

- COV: Valid / invalid username equivalence classes  
- COV: Password digit requirement class  
- COV: BVA username length boundaries (3, 20)  
- COV: Decision rules for empty fields and credential pairs  

## 2. Coverage strategy & methods

| Strategy | Method | Requirements |
|----------|--------|--------------|
| STR-EP | Equivalence partitioning | REQ-002, REQ-006 |
| STR-BVA | Boundary value analysis | REQ-001, REQ-002 |
| STR-DT | Decision table | REQ-003–006 |

## 3. Sample test cases (tool-generated, reviewed)

| ID | Technique | Title | Expected |
|----|-----------|-------|----------|
| TC-EP-empty | EP | Empty username class | username is required |
| TC-BVA-min | BVA | username min length 3 | success for usr/Pass1234 |
| TC-DT-valid | DecisionTable | valid credentials | redirect /success |
| TC-DT-wrong | DecisionTable | wrong password | invalid credentials |
| TC-ST-lock | StateTransition | 3 failures | lock message 30s |

## 4. Traceability

| Requirement | Coverage | Test case / script |
|-------------|----------|-------------------|
| REQ-003 | Empty username rule | `test_login_validation_errors[empty]` |
| REQ-005 | Valid login | `test_valid_login_success` |
| REQ-007 | Lockout | `test_account_lock_after_three_failures` |

## 5. Prompt design (tool)

See `autotestdesign/prompts/` — structure, risk, EP, BVA, decision_table templates aligned to ISO 29119-4 wording.

## 6. Test tool implementation

- **Framework:** Playwright + PyTest (`target-app-tests/test_login.py`)  
- **10 automated cases** covering validation, boundaries, success, lockout  
- Run: `pytest target-app-tests/ -v`

## 7. Results analysis

See [`target-app-tests/results/summary.md`](../target-app-tests/results/summary.md).

**Conclusion:** Designed cases map to identified coverage items; automation confirms critical paths. Improvement cycle added session-timeout case in Streamlit Improvement tab.

## 8. Evidence-based improvement

| Change | Evidence | Action |
|--------|----------|--------|
| Added 3-char user `usr` | BVA min boundary test failed | SUT accepts `usr` + `Pass1234` |
| Session timeout case | Risk of stale session | Manual case in review log |

---

*Attach screenshots of Streamlit matrix and pytest output in PDF submission.*
