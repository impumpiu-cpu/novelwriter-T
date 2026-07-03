import pytest
from pydantic import ValidationError

from app.config import Settings


def test_deploy_mode_defaults_to_selfhost():
    assert Settings.model_fields["deploy_mode"].default == "selfhost"


def test_openai_model_default_starts_with_gpt():
    assert Settings.model_fields["openai_model"].default.startswith("gpt-")


def test_llm_provider_defaults_to_openai():
    assert Settings.model_fields["llm_provider"].default == "openai"


def test_ollama_base_url_gets_v1_suffix_appended():
    settings = Settings(
        llm_provider="ollama",
        ollama_base_url="http://localhost:11434",
        _env_file=None,
    )
    assert settings.ollama_base_url == "http://localhost:11434/v1"
    assert settings.selfhost_llm_base_url == "http://localhost:11434/v1"


def test_ollama_base_url_keeps_existing_v1_suffix():
    settings = Settings(
        ollama_base_url="http://host.docker.internal:11434/v1/",
        _env_file=None,
    )
    assert settings.ollama_base_url == "http://host.docker.internal:11434/v1"


def test_selfhost_llm_properties_follow_provider_choice():
    openai_settings = Settings(
        openai_api_key="sk-test",
        openai_model="gpt-4o",
        _env_file=None,
    )
    assert openai_settings.selfhost_llm_api_key == "sk-test"
    assert openai_settings.selfhost_llm_model == "gpt-4o"

    ollama_settings = Settings(
        llm_provider="ollama",
        ollama_model="llama3.1:8b",
        ollama_api_key="",
        _env_file=None,
    )
    assert ollama_settings.selfhost_llm_model == "llama3.1:8b"
    assert ollama_settings.selfhost_llm_api_key == "ollama"


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
