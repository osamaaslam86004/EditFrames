import pytest
from pydantic import SecretStr, ValidationError

from core.config import (
    AppConfig,
    CeleryConfig,
    RedisConfig,
    SecurityConfig,
    get_settings,
)


def test_app_config_defaults():
    app = AppConfig()
    assert app.app_name == "Video Generation Studio With Kokoro"
    assert app.environment == "development"
    assert app.api_key is None


def test_app_config_enforce_production_secrets():
    # In production without API key, should raise ValueError
    with pytest.raises(ValidationError) as exc_info:
        AppConfig(environment="production", api_key=None)
    assert "API_KEY is required when ENVIRONMENT=production" in str(exc_info.value)

    # In production with API key, should succeed
    app_prod = AppConfig(
        environment="production", api_key=SecretStr("prod-secret-key-1234")
    )
    assert app_prod.api_key.get_secret_value() == "prod-secret-key-1234"


def test_security_config_defaults():
    sec = SecurityConfig()
    # Ensure api_key default is None, not a tuple (None,)
    assert sec.api_key is None or isinstance(sec.api_key, SecretStr)
    assert not isinstance(sec.api_key, tuple)
    assert sec.allow_credentials is True


def test_redis_config_no_tuples():
    redis_cfg = RedisConfig(base_url="redis://localhost:6379")
    # Ensure timeouts are integers, not tuples
    assert isinstance(redis_cfg.socket_connect_timeout, int)
    assert isinstance(redis_cfg.socket_timeout, int)
    assert redis_cfg.socket_connect_timeout == 15
    assert redis_cfg.socket_timeout == 5


def test_celery_config_defaults():
    celery_cfg = CeleryConfig()
    assert celery_cfg.celery_broker_url == "redis://localhost:6379/1"
    assert celery_cfg.celery_result_backend == "redis://localhost:6379/2"
    assert celery_cfg.task_max_retries == 2


def test_settings_load_from_env():
    settings = get_settings()
    assert settings.app is not None
    assert settings.security is not None
    assert settings.redis is not None
    assert settings.celery is not None
    assert settings.llm is not None
    assert not isinstance(settings.security.api_key, tuple)
    assert not isinstance(settings.redis.socket_timeout, tuple)
    assert not isinstance(settings.redis.socket_connect_timeout, tuple)
