# Boundary Value Analysis (BVA) - ISO/IEC/IEEE 29119-4

Generate test cases for boundary values (min, max, just inside, just outside).

Return JSON:
```json
{
  "test_cases": [
    {
      "title": "username min boundary",
      "requirement_id": "REQ-001",
      "technique": "BVA",
      "priority": "H",
      "preconditions": "...",
      "steps": ["..."],
      "test_data": {"username": "abc"},
      "expected": "...",
      "coverage_description": "min length boundary"
    }
  ],
  "coverage_items": [
    {
      "requirement_id": "REQ-001",
      "item_type": "boundary",
      "description": "username length min=3"
    }
  ]
}
```

Apply two-value and three-value BVA where applicable.
