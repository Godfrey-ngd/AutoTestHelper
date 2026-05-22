"""FR 1.1 - Structure and tag requirements."""

from __future__ import annotations

import re

from autotestdesign.core.llm_client import chat_json, has_llm, load_prompt
from autotestdesign.models.schemas import Requirement, StructuredFields


def _fallback_structure(req: Requirement) -> Requirement:
    text = req.raw_text.lower()
    structured = StructuredFields()
    for field in ("username", "password", "email", "login"):
        if field in text:
            structured.inputs.append(field)
    for m in re.finditer(r"(\d+)\s*[-–to]\s*(\d+)\s*char", text):
        structured.data_ranges.append(f"{m.group(1)}-{m.group(2)} characters")
    if "must" in text or "shall" in text or "至少" in req.raw_text:
        structured.conditions.append(req.raw_text)
    if "error" in text or "success" in text or "redirect" in text or "显示" in req.raw_text:
        structured.expected_actions.append("See requirement text for expected behavior")
    if not structured.inputs:
        structured.inputs = ["input fields per requirement"]
    if not structured.expected_actions:
        structured.expected_actions = ["System behaves per specification"]
    req.structured = structured
    if not req.title:
        req.title = req.raw_text[:80]
    return req


def structure_requirements(requirements: list[Requirement]) -> list[Requirement]:
    if not requirements:
        return []

    if has_llm():
        system = load_prompt("structure_requirement.md")
        payload = {
            "requirements": [
                {"id": r.id, "raw_text": r.raw_text, "title": r.title}
                for r in requirements
            ]
        }
        import json

        result = chat_json(system, json.dumps(payload, ensure_ascii=False))
        if result and "requirements" in result:
            mapped: dict[str, Requirement] = {}
            for item in result["requirements"]:
                rid = item.get("id") or Requirement().id
                sf = item.get("structured", {})
                mapped[rid] = Requirement(
                    id=rid,
                    raw_text=item.get("raw_text", ""),
                    title=item.get("title", ""),
                    structured=StructuredFields(
                        inputs=sf.get("inputs", []),
                        data_ranges=sf.get("data_ranges", []),
                        conditions=sf.get("conditions", []),
                        expected_actions=sf.get("expected_actions", []),
                    ),
                )
            out: list[Requirement] = []
            for r in requirements:
                out.append(mapped.get(r.id, _fallback_structure(r)))
            return out

    return [_fallback_structure(r) for r in requirements]
