# Risk Analysis Report — Login Web Module (Target Application)

**Team ID:** [填写]  
**Members:** [姓名 / 学号]  
**System under test:** `target-app/` login module  
**Tool used for assessment:** AutoTestDesign FR 2.0

---

## 1. Scope

This report analyzes risks for the **login module only** (not the AutoTestDesign tool). Requirements source: `sample_data/login_requirements.csv`.

## 2. Risk summary

| Req ID | Priority | Score | Rationale |
|--------|----------|-------|-----------|
| REQ-001 | H | 85 | Username validation — authentication input |
| REQ-002 | H | 85 | Password policy — credential security |
| REQ-003 | M | 65 | Empty username — error handling / UX |
| REQ-004 | M | 65 | Empty password — error handling |
| REQ-005 | H | 90 | Successful login — core business path |
| REQ-006 | H | 88 | Invalid credentials — security / brute force surface |
| REQ-007 | H | 92 | Account lockout — availability & security control |

## 3. Risk drivers (ISO 29119 risk-based testing)

- **Likelihood:** High for REQ-005/006 (frequent user path).
- **Impact:** High for authentication failures (unauthorized access, account denial).
- **Technical complexity:** Medium (boundary rules + lock timer).

## 4. Testing priority implications

1. Execute all **H** requirements with EP + BVA + decision table first.  
2. Automate lockout (REQ-007) and valid login (REQ-005).  
3. Manual exploratory on session timeout if added in improvement cycle.

## 5. Residual risks

- Session fixation / HTTPS not in scope for demo app.  
- Recommend production hardening: rate limiting, CAPTCHA, audit logging.

---

*Generated with AutoTestDesign; review and adjust priorities in Streamlit before PDF export.*
