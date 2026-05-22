# AutoTestDesign — Project Templates

Ready-to-use **project name**, **target app description**, and **requirements** for the Streamlit **Import** tab.  
Paste the CSV block into **Requirements (CSV id,text or one per line)** → **Format hint: auto** or **csv** → **Run full pipeline**.

---

## How to use in the UI

| Field (sidebar / project) | What to enter |
|-------------------------|---------------|
| **Project name** | Template name below (column “Project name”) |
| **Target app** | “Target app description” paragraph |
| **Requirements text box** | Entire CSV block including header `id,text` |

---

## Template 1 — Login Module (English) ★ Recommended

**Matches bundled SUT:** `target-app/` (http://127.0.0.1:5000)  
**Use for:** Assignment demo, pytest `target-app-tests/`, risk report & test plan.

| Field | Value |
|-------|--------|
| **Project name** | `Login Module Test` |
| **Target app description** | Web login module: username 3–20 chars, password 8–32 with digit, lockout after 3 failures. Valid: user01 / Pass1234 (or usr / Pass1234). |

```csv
id,text
REQ-001,The system shall accept username between 3 and 20 characters
REQ-002,The system shall accept password between 8 and 32 characters with at least one digit
REQ-003,Empty username shall show error message username is required
REQ-004,Empty password shall show error message password is required
REQ-005,Valid credentials user01 and Pass1234 shall redirect to success page
REQ-006,Invalid credentials shall show error invalid credentials
REQ-007,After three failed login attempts the account shall be locked for 30 seconds
```

**Also on disk:** `sample_data/login_requirements.csv`

---

## Template 2 — Login Module (中文)

Same rules as Template 1; requirements in Chinese for LLM structuring demos.

| Field | Value |
|-------|--------|
| **Project name** | `登录模块测试` |
| **Target app description** | Web 登录模块：用户名 3–20 字符，密码 8–32 且含数字；连续 3 次失败锁定 30 秒。有效账号 user01 / Pass1234。 |

```csv
id,text
REQ-001,系统应接受长度为 3 到 20 个字符的用户名
REQ-002,系统应接受长度为 8 到 32 个字符的密码且至少包含一个数字
REQ-003,用户名为空时应显示错误信息 username is required
REQ-004,密码为空时应显示错误信息 password is required
REQ-005,凭据 user01 与 Pass1234 正确时应跳转到成功页面
REQ-006,凭据错误时应显示 invalid credentials
REQ-007,连续三次登录失败后账户应锁定 30 秒
```

---

## Template 3 — Calculator (Basic Arithmetic)

**SUT:** Not included in repo — use for test-design-only reports or build a simple calc app later.  
**Techniques:** Strong fit for EP (valid/invalid ops), BVA (operand limits), decision table (operator + operands).

| Field | Value |
|-------|--------|
| **Project name** | `Calculator Basic Ops` |
| **Target app description** | Desktop or Web calculator: add, subtract, multiply, divide; divide-by-zero error; operands in range -999 to 999. |

```csv
id,text
REQ-001,The system shall accept numeric operand A in range -999 to 999
REQ-002,The system shall accept numeric operand B in range -999 to 999
REQ-003,The system shall support operators add subtract multiply divide
REQ-004,Division by zero shall display error Cannot divide by zero
REQ-005,Empty operand A shall display error Operand A is required
REQ-006,Empty operand B shall display error Operand B is required
REQ-007,Valid expression 12 add 3 shall display result 15
REQ-008,Non-numeric input shall display error Invalid number
```

---

## Template 4 — Todo List (CRUD)

**SUT:** Not included — typical second target app for assignments.

| Field | Value |
|-------|--------|
| **Project name** | `Todo List CRUD` |
| **Target app description** | Web todo app: create task title 1–100 chars, mark complete, delete; max 50 active tasks per user. |

```csv
id,text
REQ-001,Task title shall be between 1 and 100 characters
REQ-002,Empty task title shall show error Title is required
REQ-003,User shall create a new task and see it in the list
REQ-004,User shall mark a task as completed and show strikethrough style
REQ-005,User shall delete a task and remove it from the list
REQ-006,When 50 active tasks exist creating another shall show error Task limit reached
REQ-007,Completing a non-existent task id shall show error Task not found
REQ-008,Deleting a completed task shall remove it from both active and completed views
```

---

## Template 5 — User Registration

**SUT:** Not included — pairs well with login template for integrated test plan.

| Field | Value |
|-------|--------|
| **Project name** | `User Registration` |
| **Target app description** | Registration form: email format, password policy, confirm password match, unique email. |

```csv
id,text
REQ-001,Email shall match valid email format and be unique in the system
REQ-002,Password shall be 8 to 32 characters with at least one uppercase one lowercase and one digit
REQ-003,Confirm password shall match password field
REQ-004,Empty email shall show error Email is required
REQ-005,Empty password shall show error Password is required
REQ-006,Duplicate email shall show error Email already registered
REQ-007,Valid registration shall redirect to login page with success message
REQ-008,Password without uppercase letter shall show error Password policy not met
```

---

## Template 6 — ATM Withdrawal (Decision-table friendly)

**SUT:** Not included — good for **decision table** and **risk** demos (financial rules).

| Field | Value |
|-------|--------|
| **Project name** | `ATM Withdrawal` |
| **Target app description** | ATM: PIN 4 digits, balance check, daily limit 500, denominations 20/50/100. |

```csv
id,text
REQ-001,PIN shall be exactly 4 numeric digits
REQ-002,Incorrect PIN three times shall block card for 24 hours
REQ-003,Withdrawal amount shall be multiple of 20 and not exceed account balance
REQ-004,Single withdrawal shall not exceed daily limit of 500
REQ-005,Empty PIN shall show error PIN is required
REQ-006,Valid PIN and sufficient balance shall dispense cash and print receipt
REQ-007,Amount exceeding balance shall show error Insufficient funds
REQ-008,Amount exceeding daily limit shall show error Daily limit exceeded
```

---

## Template 7 — Minimal (3 requirements, quick demo)

Fast pipeline run for UI or performance benchmark.

| Field | Value |
|-------|--------|
| **Project name** | `Quick Demo Login` |
| **Target app description** | Minimal login: user01 / Pass1234 only. |

```csv
id,text
REQ-001,Username must be 3 to 20 characters
REQ-002,Password must be 8 to 32 characters with at least one digit
REQ-003,Valid user01 and Pass1234 redirect to success invalid show error
```

---

## Template comparison

| Template | Requirements | Best for | Works with repo `target-app` |
|----------|--------------|----------|------------------------------|
| 1 Login EN | 7 | Full assignment + automation | Yes ★ |
| 2 Login ZH | 7 | Chinese LLM demo | Yes (messages in English on SUT) |
| 3 Calculator | 8 | EP / BVA teaching | No |
| 4 Todo | 8 | CRUD test plan | No |
| 5 Registration | 8 | Security / validation | No |
| 6 ATM | 8 | Decision table + risk H | No |
| 7 Quick | 3 | Fast UI / benchmark | Partial |

---

## Import without CSV header (optional)

Same as Template 1, **Sample login requirements** style (no `id,text` line):

```text
REQ-001,The system shall accept username between 3 and 20 characters
REQ-002,The system shall accept password between 8 and 32 characters with at least one digit
REQ-003,Empty username shall show error message username is required
REQ-004,Empty password shall show error message password is required
REQ-005,Valid credentials user01 and Pass1234 shall redirect to success page
REQ-006,Invalid credentials shall show error invalid credentials
REQ-007,After three failed login attempts the account shall be locked for 30 seconds
```

Set **Format hint** to **auto**.

---

## Suggested course deliverable mapping

| Deliverable | Suggested template |
|-------------|-------------------|
| Tool demo video | Template 1 or 7 |
| Risk analysis PDF | Template 1 |
| Test plan PDF | Template 1 (+ reference Template 5 as future scope) |
| Detailed design & execution | Template 1 + `target-app-tests/` |
| Extra credit breadth | Template 3 or 6 in test plan only |

---

*Copy templates into Streamlit or save as `sample_data/<name>_requirements.csv` for reuse.*
