from app.api.deps import _build_llm
from app.core.config import Settings
from app.llm.azure import AzureLLM
from app.llm.fake import FakeLLM


def test_builds_fake_llm_by_default():
    settings = Settings(_env_file=None)

    assert isinstance(_build_llm(settings), FakeLLM)


def test_builds_azure_llm_when_selected():
    settings = Settings(
        _env_file=None,
        llm_provider="azure",
        llm_api_key="test-key",
        llm_base_url="https://example.test/openai/v1/",
        llm_model="test-model",
    )

    assert isinstance(_build_llm(settings), AzureLLM)
