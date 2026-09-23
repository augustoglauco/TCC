from app.config import Settings, get_settings


def test_settings_load_with_defaults():
    settings = Settings(_env_file=None)
    assert settings.app_env == "development"
    assert settings.local_model_name


def test_get_settings_is_cached():
    assert get_settings() is get_settings()


def test_settings_have_router_defaults():
    settings = Settings(_env_file=None)
    assert settings.router_complexity_strategy == "heuristic"
    assert settings.local_llm_timeout_s == 30.0
    assert settings.external_llm_timeout_s == 30.0
    assert settings.external_model_price_per_1k_input_tokens == 0.0
    assert settings.external_model_price_per_1k_output_tokens == 0.0


def test_settings_external_model_points_to_openrouter():
    settings = Settings(_env_file=None)
    assert settings.external_model_base_url == "https://openrouter.ai/api/v1"


def test_settings_have_stt_model_size_default():
    settings = Settings(_env_file=None)
    assert settings.stt_model_size == "small"


def test_settings_have_crawler_defaults():
    settings = Settings(_env_file=None)
    assert settings.crawler_max_pages == 20
    assert settings.crawler_confidence_threshold == 0.7


def test_settings_tem_defaults_de_agendamento():
    settings = Settings(_env_file=None)

    assert settings.calendar_mcp_url == "http://127.0.0.1:8090/mcp"
    assert settings.agendamento_timezone == "America/Sao_Paulo"
    assert settings.agendamento_expediente_dias == "seg-sex"
    assert settings.agendamento_expediente_inicio == "09:00"
    assert settings.agendamento_expediente_fim == "18:00"
