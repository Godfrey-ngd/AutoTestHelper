# Equivalence Partitioning (EP) - ISO/IEC/IEEE 29119-4

Generate test cases using equivalence class partitioning.

Return JSON:
```json
{
  "test_cases": [
    {
      "title": "case title",
      "requirement_id": "REQ-001",
      "technique": "EP",
      "priority": "H",
      "preconditions": "...",
      "steps": ["step1", "step2"],
      "test_data": {"username": "valid_user"},
      "expected": "expected result",
      "coverage_description": "valid equivalence class"
    }
  ],
  "coverage_items": [
    {
      "requirement_id": "REQ-001",
      "item_type": "equivalence_class",
      "description": "valid username class"
    }
  ]
}
```

Include valid and invalid equivalence classes with representative values.
