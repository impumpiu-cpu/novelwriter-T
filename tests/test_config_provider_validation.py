import pytest
from pydantic import ValidationError

from app.config import Settings


def test_deploy_mode_defaults_to_selfhost():
    assert Settings.model_fields["deploy_mode"].default == "selfhost"


def test_openai_model_default_starts_with_gpt():
    assert Settings.model_fields["openai_model"].default.startswith("gpt-")


def test_settings_do_not_keep_unwired_provider_fields():
    model_fields = Settings.model_fields

    assert "deepseek_api_key" not in model_fields
    assert "deepseek_base_url" not in model_fields
    assert "deepseek_model" not in model_fields


def test_lorebook_settings_only_keep_live_defaults():
    model_fields = Settings.model_fields

    assert model_fields["lore_max_total_tokens"].default == 2000
    assert model_fields["lore_default_priority"].default == 100
    assert model_fields["lore_default_token_budget"].default == 500

    assert "lore_protagonist_priority" not in model_fields
    assert "lore_item_priority" not in model_fields
    assert "lore_location_priority" not in model_fields
    assert "lore_faction_priority" not in model_fields


def test_settings_do_not_keep_dead_outline_generation_knobs():
    assert "outline_chunk_size" not in Settings.model_fields


def test_settings_validate_background_llm_lane_does_not_exceed_global_capacity():
    with pytest.raises(ValidationError, match="max_background_concurrent_llm_calls cannot exceed"):
        Settings(
            max_concurrent_llm_calls=1,
            max_background_concurrent_llm_calls=2,
            _env_file=None,
        )
