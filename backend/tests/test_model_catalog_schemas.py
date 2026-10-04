from datetime import UTC, datetime

from app.models.model_catalog import CharacteristicsRefreshRequest, ModelCharacteristicsResponse


def test_model_characteristics_response_aceita_campos_opcionais_none():
    resp = ModelCharacteristicsResponse(
        source="ollama",
        tag="llama3.1:8b",
        is_multimodal=False,
        input_modalities=["text"],
        output_modalities=["text"],
        context_length=131072,
        parameter_size="8.0B",
        quantization="Q4_K_M",
        pricing_prompt_per_1k=None,
        pricing_completion_per_1k=None,
        knowledge_cutoff=None,
        fetched_at=datetime.now(UTC),
    )
    assert resp.is_multimodal is False
    assert resp.pricing_prompt_per_1k is None


def test_characteristics_refresh_request_exige_tag_nao_vazia():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        CharacteristicsRefreshRequest(source="openrouter", tag="")
