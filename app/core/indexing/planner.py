from __future__ import annotations

AUTO_INDEX_PLAN_IMMEDIATE = "immediate"
AUTO_INDEX_PLAN_DEFERRED = "deferred"
AUTO_INDEX_PLAN_SKIP_AUTO = "skip_auto"
AUTO_INDEX_PLANS = frozenset(
    {
        AUTO_INDEX_PLAN_IMMEDIATE,
        AUTO_INDEX_PLAN_DEFERRED,
        AUTO_INDEX_PLAN_SKIP_AUTO,
    }
)


def should_enqueue_window_index_build(auto_index_plan: str | None) -> bool:
    return should_enqueue_window_index_build_immediately(auto_index_plan)


def should_enqueue_window_index_build_immediately(auto_index_plan: str | None) -> bool:
    return auto_index_plan == AUTO_INDEX_PLAN_IMMEDIATE


def should_enqueue_window_index_build_deferred(auto_index_plan: str | None) -> bool:
    return auto_index_plan in {
        AUTO_INDEX_PLAN_DEFERRED,
    }
