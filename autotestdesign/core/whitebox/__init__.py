from autotestdesign.core.whitebox.state_model import build_login_state_model, LOGIN_STATE_DIAGRAM
from autotestdesign.core.whitebox.models import (
    CFGEdge,
    CFGNode,
    ControlFlowGraph,
    CoverageTarget,
    StateMachine,
    StateNode,
    Transition,
    WhiteboxResult,
)
from autotestdesign.core.whitebox.model_parser import detect_and_parse
from autotestdesign.core.whitebox.llm_derive import derive_state_machine, derive_control_flow_graph
from autotestdesign.core.whitebox.coverage import run_coverage, CRITERIA_MAP
from autotestdesign.core.whitebox.optimizer import (
    chinese_postman_tour,
    greedy_set_cover,
    merge_paths,
    optimize_result,
    risk_weighted_sort,
)

__all__ = [
    # Legacy
    "build_login_state_model",
    "LOGIN_STATE_DIAGRAM",
    # Models
    "StateMachine",
    "StateNode",
    "Transition",
    "ControlFlowGraph",
    "CFGNode",
    "CFGEdge",
    "CoverageTarget",
    "WhiteboxResult",
    # Parser
    "detect_and_parse",
    # LLM
    "derive_state_machine",
    "derive_control_flow_graph",
    # Coverage
    "run_coverage",
    "CRITERIA_MAP",
    # Optimizer
    "chinese_postman_tour",
    "greedy_set_cover",
    "merge_paths",
    "optimize_result",
    "risk_weighted_sort",
]
