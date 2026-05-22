# Risk Assessment Prompt

Assess test risk per requirement using ISO 29119 / ISTQB risk-based testing.

Return JSON:
```json
{
  "risks": [
    {
      "requirement_id": "REQ-001",
      "score": 75,
      "priority": "H",
      "reason": "explanation"
    }
  ]
}
```

Scoring guide:
- 80-100, priority H: security, authentication, data loss, financial
- 50-79, priority M: validation, usability impact
- 0-49, priority L: cosmetic, low-impact UI

Priority must be exactly H, M, or L.
