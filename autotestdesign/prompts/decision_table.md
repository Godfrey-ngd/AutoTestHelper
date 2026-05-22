# Decision Table Testing - ISO/IEC/IEEE 29119-4

Build a decision table from conditions and actions, then derive test cases.

Return JSON:
```json
{
  "decision_table": {
    "conditions": ["C1: username valid", "C2: password valid"],
    "actions": ["A1: allow login", "A2: show error"]
  },
  "test_cases": [
    {
      "title": "valid credentials login",
      "requirement_id": "REQ-001",
      "technique": "DecisionTable",
      "priority": "H",
      "preconditions": "...",
      "steps": ["..."],
      "test_data": {"username": "user01", "password": "Pass1234"},
      "expected": "redirect to success",
      "coverage_description": "C1=Y,C2=Y -> A1"
    }
  ],
  "coverage_items": [
    {
      "requirement_id": "REQ-001",
      "item_type": "decision_rule",
      "description": "rule combination C1=Y,C2=Y"
    }
  ]
}
```

Cover combinations that differ in outcome; avoid redundant rules.
