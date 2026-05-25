"""Unified domain models for AutoTestDesign."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import json
import threading
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class Priority(str, Enum):
    HIGH = "H"
    MEDIUM = "M"
    LOW = "L"


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


_seq_counters: dict[str, int] = {}
_seq_lock = threading.Lock()


def _next_id(prefix: str) -> str:
    """Session-scoped sequential ID: TC-001, TC-002, etc."""
    with _seq_lock:
        _seq_counters[prefix] = _seq_counters.get(prefix, 0) + 1
        n = _seq_counters[prefix]
    return f"{prefix}-{n:03d}"


def seed_ids_from_project(project: "Project") -> None:
    """Seed sequential ID counters from existing project items.

    Call after loading a project to avoid ID collisions.
    """
    for prefix, items in [
        ("TC", project.test_cases),
        ("COV", project.coverage_items),
        ("STR", project.strategies),
    ]:
        max_n = 0
        for item in items:
            try:
                n = int(item.id.split("-", 1)[1])
                max_n = max(max_n, n)
            except (ValueError, IndexError):
                pass
        _seq_counters[prefix] = max(_seq_counters.get(prefix, 0), max_n)


class RiskWeights(BaseModel):
    """Configurable risk scoring weights for FR 2.0."""

    business_impact: float = Field(default=0.40, ge=0.0, le=1.0)
    failure_probability: float = Field(default=0.35, ge=0.0, le=1.0)
    detectability: float = Field(default=0.25, ge=0.0, le=1.0)


class StructuredFields(BaseModel):
    inputs: list[str] = Field(default_factory=list)
    data_ranges: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    expected_actions: list[str] = Field(default_factory=list)


class Requirement(BaseModel):
    id: str = Field(default_factory=lambda: _id("REQ"))
    raw_text: str = ""
    title: str = ""
    structured: StructuredFields = Field(default_factory=StructuredFields)


class RiskAssessment(BaseModel):
    requirement_id: str
    score: int = Field(ge=0, le=100, default=50)
    priority: Priority = Priority.MEDIUM
    reason: str = ""


class CoverageItem(BaseModel):
    id: str = Field(default_factory=lambda: _next_id("COV"))
    requirement_id: str = ""
    item_type: str = "functional"
    description: str = ""


class TestStrategy(BaseModel):
    id: str = Field(default_factory=lambda: _next_id("STR"))
    technique: str = ""
    rationale: str = ""
    coverage_ids: list[str] = Field(default_factory=list)
    requirement_ids: list[str] = Field(default_factory=list)


class TraceLink(BaseModel):
    requirement_id: str = ""
    coverage_id: str = ""
    strategy_id: str = ""
    test_case_id: str = ""


def _coerce_test_data(value: Any) -> dict[str, str]:
    """LLM JSON often uses numbers/bools; schema requires dict[str, str]."""
    if not value:
        return {}
    if not isinstance(value, dict):
        return {"value": str(value)}
    out: dict[str, str] = {}
    for key, val in value.items():
        k = str(key)
        if val is None:
            out[k] = ""
        elif isinstance(val, bool):
            out[k] = "true" if val else "false"
        elif isinstance(val, (list, dict)):
            out[k] = json.dumps(val, ensure_ascii=False)
        else:
            out[k] = str(val)
    return out


def _coerce_steps(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(s) for s in value]
    if isinstance(value, str) and value.strip():
        return [value]
    return []


class TestCase(BaseModel):
    id: str = Field(default_factory=lambda: _next_id("TC"))
    requirement_id: str = ""
    title: str = ""
    technique: str = ""
    priority: Priority = Priority.MEDIUM
    preconditions: str = ""
    steps: list[str] = Field(default_factory=list)
    test_data: dict[str, str] = Field(default_factory=dict)
    expected: str = ""
    risk_score: int = 50
    coverage_ids: list[str] = Field(default_factory=list)
    strategy_id: str = ""
    status: str = Field(default="active", description="active | invalid — for evidence-based improvement")

    @field_validator("test_data", mode="before")
    @classmethod
    def validate_test_data(cls, value: Any) -> dict[str, str]:
        return _coerce_test_data(value)

    @field_validator("steps", mode="before")
    @classmethod
    def validate_steps(cls, value: Any) -> list[str]:
        return _coerce_steps(value)

    @field_validator("risk_score", mode="before")
    @classmethod
    def validate_risk_score(cls, value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 50


class ReviewEvent(BaseModel):
    id: str = Field(default_factory=lambda: _id("REV"))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    entity_type: str = ""
    entity_id: str = ""
    field_name: str = ""
    old_value: str = ""
    new_value: str = ""
    note: str = ""


class Project(BaseModel):
    id: str = Field(default_factory=lambda: _id("PRJ"))
    name: str = "Untitled Project"
    target_app_description: str = ""
    risk_weights: RiskWeights = Field(default_factory=RiskWeights)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    requirements: list[Requirement] = Field(default_factory=list)
    risks: list[RiskAssessment] = Field(default_factory=list)
    coverage_items: list[CoverageItem] = Field(default_factory=list)
    strategies: list[TestStrategy] = Field(default_factory=list)
    test_cases: list[TestCase] = Field(default_factory=list)
    trace_links: list[TraceLink] = Field(default_factory=list)
    review_events: list[ReviewEvent] = Field(default_factory=list)
    state_diagram: Optional[str] = None
    optimized_case_ids: list[str] = Field(default_factory=list)
    whitebox_result: Optional[dict] = None
