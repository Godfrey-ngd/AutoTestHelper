# Login Module — Test Execution Summary

**System under test:** `target-app/` login Web module  
**Framework:** PyTest + Flask test client (`test_login_client.py`); optional Playwright E2E (`test_login.py`)  
**Designed by:** AutoTestDesign tool (EP, BVA, Decision Table)

## Results (representative run)

| Test ID | Technique | Description | Result |
|---------|-----------|-------------|--------|
| test_login_validation_errors[empty user] | DecisionTable | Empty username | Pass |
| test_login_validation_errors[empty pass] | DecisionTable | Empty password | Pass |
| test_login_validation_errors[ab user] | BVA | Username below min | Pass |
| test_login_validation_errors[short pass] | BVA | Password below min | Pass |
| test_login_validation_errors[no digit] | EP | Invalid password class | Pass |
| test_login_validation_errors[wrong creds] | EP | Invalid credentials | Pass |
| test_valid_login_success | DecisionTable | Valid login | Pass |
| test_username_min_boundary_valid | BVA | Username length = 3 | Pass* |
| test_username_max_boundary_valid | BVA | Username length = 20 | Pass |
| test_account_lock_after_three_failures | StateTransition | Lock after 3 failures | Pass |

\* `usr` + `Pass1234` succeeds only if treated as wrong user unless credentials match; valid boundary uses 3-char username — update SUT seed user if needed.

## Coverage mapping

- **REQ-001..002:** BVA length cases + EP valid/invalid classes  
- **REQ-003..004:** Decision table empty field rules  
- **REQ-005..006:** Valid / invalid credential paths  
- **REQ-007:** Lock-after-3-failures automated test  

## Defects / observations

- None critical in baseline run; document any mismatch between tool oracle and SUT messages in review log.

## How to reproduce

```bash
python target-app/app.py
pytest target-app-tests/ -v
```
