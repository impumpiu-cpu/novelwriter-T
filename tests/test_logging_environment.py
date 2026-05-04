import logging

import structlog


def _last_processor():
    cfg = structlog.get_config()
    processors = cfg.get("processors") or []
    assert processors, "structlog processors not configured"
    return processors[-1]


def test_configure_logging_uses_json_renderer_for_production_values():
    from app.config import Settings
    from app.logging_setup import configure_logging

    for value in ["production", "prod", " Production ", "PROD"]:
        settings = Settings(environment=value)
        structlog.reset_defaults()
        configure_logging(is_production=settings.is_production)
        assert isinstance(_last_processor(), structlog.processors.JSONRenderer)

    structlog.reset_defaults()


def test_configure_logging_uses_console_renderer_for_non_production_values():
    from app.config import Settings
    from app.logging_setup import configure_logging

    for value in ["dev", "staging", "local", ""]:
        settings = Settings(environment=value)
        structlog.reset_defaults()
        configure_logging(is_production=settings.is_production)
        assert isinstance(_last_processor(), structlog.dev.ConsoleRenderer)

    structlog.reset_defaults()


def test_configure_logging_installs_root_handler_when_process_has_none():
    from app.logging_setup import configure_logging

    root_logger = logging.getLogger()
    original_handlers = list(root_logger.handlers)
    original_level = root_logger.level
    try:
        root_logger.handlers.clear()
        structlog.reset_defaults()

        configure_logging(is_production=True)

        assert root_logger.handlers
        assert root_logger.level == logging.INFO
    finally:
        root_logger.handlers.clear()
        root_logger.handlers.extend(original_handlers)
        root_logger.setLevel(original_level)
        structlog.reset_defaults()
