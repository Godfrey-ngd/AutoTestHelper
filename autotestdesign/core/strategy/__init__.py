"""Strategy configuration subpackage: recommend, preview, suite management, test planning."""
from autotestdesign.core.strategy.preview import estimate_case_count, estimate_coverage
from autotestdesign.core.strategy.recommender import (
    auto_recommend,
    get_technique_metadata,
    recommend_for_requirement,
    recommend_for_risk,
)
from autotestdesign.core.strategy.suite_manager import (
    assign_to_suite,
    create_suite,
    delete_suite,
    get_suite_map,
    remove_from_suite,
    reorder_suites,
    update_suite,
)
from autotestdesign.core.strategy.test_planner import (
    auto_generate_plan,
    get_phases,
    get_plan_summary,
    recalculate_effort,
)

__all__ = [
    "auto_recommend",
    "get_technique_metadata",
    "recommend_for_requirement",
    "recommend_for_risk",
    "estimate_case_count",
    "estimate_coverage",
    "create_suite",
    "update_suite",
    "delete_suite",
    "assign_to_suite",
    "remove_from_suite",
    "reorder_suites",
    "get_suite_map",
    "auto_generate_plan",
    "get_phases",
    "get_plan_summary",
    "recalculate_effort",
]
