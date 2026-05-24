"""OpenAI-compatible LLM client with rule-based fallback."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Optional


_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


def _read_env_file() -> dict[str, str]:
    """Read .env into a dict directly — no dotenv, no os.environ."""
    result: dict[str, str] = {}
    if not _ENV_PATH.exists():
        return result
    for line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and val:
            result[key] = val
    return result


def _load_env_file() -> None:
    """Manually load .env to avoid dotenv path resolution issues."""
    for key, val in _read_env_file().items():
        os.environ[key] = val


_load_env_file()

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"


def load_prompt(name: str) -> str:
    path = PROMPTS_DIR / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def _extract_json(text: str) -> Any:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            import json_repair

            return json_repair.loads(text)
        except Exception:
            return None


def chat_json(
    system: str,
    user: str,
    *,
    temperature: float = 0.2,
) -> Optional[Any]:
    # Read directly from .env file to avoid any os.environ interference
    env = _read_env_file()
    api_key = env.get("OPENAI_API_KEY", "").strip()
    base_url = env.get("OPENAI_BASE_URL", "https://api.openai.com/v1")

    # Debug: log actual values at call time
    _log_path = Path(__file__).resolve().parents[2] / "llm_debug.log"
    with open(_log_path, "a") as _f:
        _f.write(f"api_key={api_key[:15]}... base_url={base_url}\n")

    if not api_key:
        return None

    import httpx
    from openai import OpenAI

    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
        http_client=httpx.Client(timeout=120.0),
    )
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    response = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content or ""
    return _extract_json(content)


def has_llm() -> bool:
    return bool(_read_env_file().get("OPENAI_API_KEY", "").strip())
