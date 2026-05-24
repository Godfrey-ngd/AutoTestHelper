"""FR 1.0 - Import requirements from CSV, text, or paste."""

from __future__ import annotations

import csv
import io
import re
from typing import Optional

from autotestdesign.models.schemas import Requirement


def import_from_csv(content: str) -> list[Requirement]:
    """Parse CSV with columns id,text or id,title,text."""
    reader = csv.DictReader(io.StringIO(content.strip()))
    requirements: list[Requirement] = []
    for row in reader:
        rid = (row.get("id") or row.get("ID") or "").strip()
        text = (
            row.get("text")
            or row.get("Text")
            or row.get("requirement")
            or row.get("description")
            or ""
        ).strip()
        title = (row.get("title") or row.get("Title") or "").strip()
        if not text and title:
            text = title
        if not text:
            continue
        req = Requirement(
            id=rid if rid else Requirement().id,
            raw_text=text,
            title=title or text[:80],
        )
        requirements.append(req)
    return requirements


def import_from_text(content: str) -> list[Requirement]:
    """One requirement per non-empty line, or numbered items."""
    lines = content.strip().splitlines()
    requirements: list[Requirement]
    requirements = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^(?:REQ[-_]?\d+|R\d+|\d+)[.:),\s]+(.+)$", line, re.I)
        if m:
            text = m.group(1).strip()
            req_id = m.group(0).removesuffix(m.group(1)).rstrip(".:), ") or Requirement().id
        else:
            text = line
            req_id = Requirement().id
        requirements.append(
            Requirement(id=req_id, raw_text=text, title=text[:80])
        )
    return requirements


def parse_paste(content: str, source_hint: str = "auto") -> list[Requirement]:
    if source_hint == "csv" or ("," in content and "id" in content.lower()[:200]):
        try:
            reqs = import_from_csv(content)
            if reqs:
                return reqs
        except Exception:
            pass
    return import_from_text(content)
