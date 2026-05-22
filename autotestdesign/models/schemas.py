"""Unified domain models for AutoTestDesign."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class Priority(str, Enum):
    HIGH = "H"
    MEDIUM = "M"
    LOW = "L"


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


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
    id: str = Field(default_factory=lambda: _id("COV"))
    requirement_id: str = ""
    item_type: str = "functional"
    description: str = ""


class TestStrategy(BaseModel):
    id: str = Field(default_factory=lambda: _id("STR"))
    technique: str = ""
    rationale: str = ""
    coverage_ids: list[str] = Field(default_factory=list)
    requirement_ids: list[str] = Field(default_factory=list)


class TraceLink(BaseModel):
    requirement_id: str = ""
    coverage_id: str = ""
    strategy_id: str = ""
    test_case_id: str = ""


class TestCase(BaseModel):
    id: str = Field(default_factory=lambda: _id("TC"))
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
