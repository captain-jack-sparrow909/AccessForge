from accessforge.ai.configuration import effective_base_url, validated_provider_setup
from accessforge.core.config import Settings
from accessforge.db.models import ModelProviderConfig


def test_deepseek_configuration_uses_deployment_model_and_endpoint_defaults() -> None:
    settings = Settings(
        deepseek_api_base="https://deepseek.example.test/v1",
        deepseek_fast_model="fast-test-model",
        deepseek_reasoning_model="reasoning-test-model",
    )
    setup = validated_provider_setup(
        provider_type="deepseek",
        credential_mode="byok",
        base_url=None,
        fast_model=None,
        reasoning_model=None,
        vision_model=None,
        embedding_model=None,
        allowed_data_categories=["project_text"],
        settings=settings,
    )
    config = ModelProviderConfig(
        owner_id="test-owner",
        label="Test DeepSeek configuration",
        provider_type=setup.provider_type,
        credential_mode=setup.credential_mode,
        fast_model=setup.fast_model,
        reasoning_model=setup.reasoning_model,
        allowed_data_categories=setup.allowed_data_categories,
    )

    assert setup.fast_model == "fast-test-model"
    assert setup.reasoning_model == "reasoning-test-model"
    assert effective_base_url(config, settings) == "https://deepseek.example.test/v1"
