# NFR — Performance Analysis

## Target

Assignment NFR: test case generation **≤ 2 seconds** (best effort).

## Measurement

Run: `python scripts/benchmark_pipeline.py`

**Configuration:** Rule-based fallback (no `OPENAI_API_KEY`), 7 login requirements, full pipeline (structure + risk + 3 techniques).

## Expected results (rule-based)

| Phase | Typical |
|-------|---------|
| Structure | &lt; 50 ms |
| Risk | &lt; 20 ms |
| Techniques (parallel) | &lt; 200 ms |
| **Total P95** | **&lt; 500 ms** |

## LLM mode

With OpenAI API, latency depends on network and model (often 3–15s). Mitigations documented:

1. Cache structured requirements per project  
2. Parallel technique calls (implemented)  
3. Use `gpt-4o-mini` or smaller model  
4. Generate per-requirement on demand vs full suite  

## Usability / Security / Maintainability

- **UX:** Streamlit 8-tab wizard with inline editors  
- **Security:** API keys via `.env` only  
- **Maintainability:** Prompts externalized; Pydantic schemas; modular `core/`
