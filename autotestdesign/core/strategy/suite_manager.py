"""CRUD operations for test suites."""
from __future__ import annotations

from autotestdesign.models.schemas import Project, TestSuite


def create_suite(
    project: Project,
    name: str,
    description: str = "",
    requirement_ids: list[str] | None = None,
) -> TestSuite:
    suite = TestSuite(
        name=name,
        description=description,
        requirement_ids=requirement_ids or [],
    )
    project.suites.append(suite)
    return suite


def update_suite(project: Project, suite_id: str, **kwargs) -> TestSuite | None:
    for suite in project.suites:
        if suite.id == suite_id:
            for key, value in kwargs.items():
                if hasattr(suite, key):
                    setattr(suite, key, value)
            return suite
    return None


def delete_suite(project: Project, suite_id: str) -> bool:
    project.suites = [s for s in project.suites if s.id != suite_id]
    return True


def assign_to_suite(
    project: Project, suite_id: str, requirement_ids: list[str]
) -> TestSuite | None:
    for suite in project.suites:
        if suite.id == suite_id:
            existing = set(suite.requirement_ids)
            existing.update(requirement_ids)
            suite.requirement_ids = list(existing)
            return suite
    return None


def remove_from_suite(
    project: Project, suite_id: str, requirement_ids: list[str]
) -> TestSuite | None:
    for suite in project.suites:
        if suite.id == suite_id:
            suite.requirement_ids = [
                r for r in suite.requirement_ids if r not in requirement_ids
            ]
            return suite
    return None


def reorder_suites(project: Project, ordered_ids: list[str]) -> None:
    id_to_priority = {sid: i for i, sid in enumerate(ordered_ids)}
    for suite in project.suites:
        if suite.id in id_to_priority:
            suite.priority = id_to_priority[suite.id]


def get_suite_map(project: Project) -> dict[str, str]:
    """Return mapping of requirement_id -> suite_name for all suites."""
    mapping: dict[str, str] = {}
    for suite in project.suites:
        for rid in suite.requirement_ids:
            mapping[rid] = suite.name
    return mapping
