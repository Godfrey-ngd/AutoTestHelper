"""Review event tracking for interactive design."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from autotestdesign.models.schemas import Project, ReviewEvent


def log_review(
    project: Project,
    entity_type: str,
    entity_id: str,
    field_name: str,
    old_value: Any,
    new_value: Any,
    note: str = "",
) -> None:
    project.review_events.append(
        ReviewEvent(
            timestamp=datetime.now(timezone.utc),
            entity_type=entity_type,
            entity_id=entity_id,
            field_name=field_name,
            old_value=str(old_value),
            new_value=str(new_value),
            note=note,
        )
    )
