# SPDX-FileCopyrightText: 2026 Isaac.X.Ω.Yuan
# SPDX-License-Identifier: AGPL-3.0-only

"""Regression tests for explicit copilot prompt/tool runtime contracts."""

from app.core.copilot.research_tools import RESEARCH_TOOL_CATALOG, get_research_tool_spec


def test_research_prompt_build_exposes_named_sections(db, novel, entities, chapters):
    from app.core.copilot.prompting import build_copilot_system_prompt_build
    from app.core.copilot.scope import gather_evidence, load_scope_snapshot

    snapshot = load_scope_snapshot(db, novel, "research", "whole_book", None)
    evidence = gather_evidence(db, novel, snapshot, None)
    build = build_copilot_system_prompt_build(
        snapshot,
        evidence,
        "whole_book",
        "zh",
        {
            "context_json": {"surface": "atlas", "tab": "systems"},
            "display_title": "全书探索",
        },
        "task_query",
    )

    assert build.prompt_id == "research_assistant"
    assert build.section_ids == [
        "assistant_identity",
        "current_task",
        "workbench_context",
        "turn_behavior",
        "language_rules",
        "world_model",
        "backend_evidence",
        "output_contract",
        "response_rules",
    ]
    world_model_section = next(
        section for section in build.to_debug_dict()["sections"] if section["id"] == "world_model"
    )
    assert world_model_section["content_kind"] == "dynamic"
    assert "snapshot.entities" in world_model_section["depends_on"]
    assert "## 世界模型" in build.prompt_text


def test_smalltalk_prompt_build_stays_on_light_sections(db, novel, entities):
    from app.core.copilot.prompting import build_copilot_system_prompt_build
    from app.core.copilot.scope import load_scope_snapshot

    snapshot = load_scope_snapshot(
        db, novel, "current_entity", "current_entity", {"entity_id": entities[0].id}
    )
    build = build_copilot_system_prompt_build(
        snapshot,
        [],
        "current_entity",
        "zh",
        {
            "context_json": {
                "surface": "studio",
                "stage": "entity",
                "entity_id": entities[0].id,
            },
            "display_title": entities[0].name,
        },
        "smalltalk",
    )

    assert build.prompt_id == "workbench_assistant"
    assert "world_model" not in build.section_ids
    assert build.to_debug_dict()["preload_world_context"] is False


def test_tool_loop_prompt_build_exposes_tool_and_workflow_sections(db, novel, entities):
    from app.core.copilot.prompting import build_tool_loop_system_prompt_build
    from app.core.copilot.scope import load_scope_snapshot

    snapshot = load_scope_snapshot(
        db, novel, "current_entity", "current_entity", {"entity_id": entities[0].id}
    )
    build = build_tool_loop_system_prompt_build(
        snapshot,
        "current_entity",
        "en",
        {"context_json": {"entity_id": entities[0].id}, "display_title": entities[0].name},
        "task_query",
    )

    tools_section = next(
        section for section in build.to_debug_dict()["sections"] if section["id"] == "tools"
    )
    workflow_section = next(
        section
        for section in build.to_debug_dict()["sections"]
        if section["id"] == "suggested_workflow"
    )
    assert build.prompt_id == "tool_loop"
    assert "tools" in build.section_ids
    assert tools_section["content_kind"] == "static"
    assert workflow_section["content_kind"] == "dynamic"
    assert "## Tools" in build.prompt_text
    assert "open_many" in build.prompt_text


def test_research_tool_catalog_carries_runtime_metadata():
    find_spec = get_research_tool_spec("find")
    open_spec = get_research_tool_spec("open")
    open_many_spec = get_research_tool_spec("open_many")
    refresh_spec = get_research_tool_spec("load_scope_snapshot")
    read_spec = get_research_tool_spec("read")

    assert [schema["function"]["name"] for schema in RESEARCH_TOOL_CATALOG.tool_schemas] == [
        "load_scope_snapshot",
        "find",
        "open",
        "open_many",
        "read",
    ]
    assert find_spec is not None
    assert find_spec.runtime.read_only is True
    assert find_spec.runtime.auto_follow_up_hint == "open_first_chapter_pack"
    assert open_spec is not None
    assert open_spec.runtime.snapshot_policy == "workspace_memory"
    assert open_many_spec is not None
    assert open_many_spec.runtime.snapshot_policy == "workspace_memory"
    assert refresh_spec is not None
    assert refresh_spec.runtime.execution_path == "runtime"
    assert read_spec is not None
    assert read_spec.runtime.snapshot_policy == "live_read"
