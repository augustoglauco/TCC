from app.config import Settings, get_settings


def test_settings_load_with_defaults():
    settings = Settings(_env_file=None)
    assert settings.app_env == "development"
    assert settings.local_model_name


def test_get_settings_is_cached():
    assert get_settings() is get_settings()
