from pathlib import Path

import pytest

from app.stt.whisper_client import SttIndisponivelError, WhisperSttClient

_FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.mark.gpu
async def test_transcreve_wav():
    client = WhisperSttClient(model_size="small")
    audio_bytes = (_FIXTURES_DIR / "stt_sample.wav").read_bytes()

    texto = await client.transcribe(audio_bytes)

    assert "agendar" in texto.lower()


@pytest.mark.gpu
async def test_transcreve_mp3():
    client = WhisperSttClient(model_size="small")
    audio_bytes = (_FIXTURES_DIR / "stt_sample.mp3").read_bytes()

    texto = await client.transcribe(audio_bytes)

    assert "agendar" in texto.lower()


@pytest.mark.gpu
async def test_erro_de_infraestrutura_vira_stt_indisponivel_error():
    # Tamanho de modelo inexistente força falha no carregamento — verifica que
    # o wrapper embrulha o erro em `SttIndisponivelError` (não propaga a
    # exceção interna do faster-whisper/huggingface_hub).
    client = WhisperSttClient(model_size="modelo-que-nao-existe-8x")

    with pytest.raises(SttIndisponivelError):
        await client.transcribe(b"conteudo-qualquer")
