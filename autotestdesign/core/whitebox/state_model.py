"""FR 4.0 - State transition model and full-state coverage sequence."""

from __future__ import annotations

from autotestdesign.models.schemas import Project, TestCase


LOGIN_STATE_DIAGRAM = """stateDiagram-v2
    [*] --> LoggedOut
    LoggedOut --> LoggingIn: submit_credentials
    LoggingIn --> LoggedIn: valid_credentials
    LoggingIn --> LoggedOut: invalid_credentials
    LoggingIn --> Locked: three_failures
    Locked --> LoggedOut: timeout_30s
    LoggedIn --> LoggedOut: logout
"""


def build_login_state_model(project: Project) -> tuple[str, list[TestCase]]:
    """Attach state diagram and generate state-covering test sequence."""
    project.state_diagram = LOGIN_STATE_DIAGRAM
    transitions = [
        ("LoggedOut to LoggingIn", "submit empty or filled form"),
        ("LoggingIn to LoggedIn", "valid user01 / Pass1234"),
        ("LoggingIn to LoggedOut", "invalid credentials"),
        ("LoggingIn to Locked", "3 consecutive failures"),
        ("Locked to LoggedOut", "wait 30 seconds"),
        ("LoggedIn to LoggedOut", "click logout"),
    ]
    cases: list[TestCase] = []
    req_id = project.requirements[0].id if project.requirements else ""
    for i, (title, action) in enumerate(transitions, 1):
        cases.append(
            TestCase(
                title=f"ST-{i}: {title}",
                requirement_id=req_id,
                technique="StateTransition",
                preconditions=f"System in state before: {title.split(' to ')[0]}",
                steps=[action],
                expected=f"Reach state: {title.split(' to ')[1]}",
            )
        )
    return LOGIN_STATE_DIAGRAM, cases
