"""Wrapper de STT (R5) via faster-whisper, rodando na mesma GPU do modelo local.

Decisão registrada em `docs/ARCHITECTURE.md` §5/§7: STT local-first, sem
lógica automática de troca de tamanho de modelo por VRAM disponível.
"""

import asyncio
import io
from typing import Protocol

from faster_whisper import WhisperModel


class SttIndisponivelError(Exception):
    """Falha de infraestrutura ao carregar o modelo ou transcrever o áudio.

    Análogo a `LocalBackendIndisponivelError` do orchestrator — erro de
    infraestrutura local, não "áudio ilegível por conteúdo".
    """


class SttClient(Protocol):
    async def transcribe(self, audio_bytes: bytes) -> str: ...


class WhisperSttClient:
    """Cliente STT local via faster-whisper.

    Suporta qualquer formato de áudio que o ffmpeg/PyAV consiga decodificar
    (inclui wav e mp3, detectados a partir dos bytes — não pela extensão).
    """

    def __init__(
        self,
        model_size: str,
        # MVP: GPU fixa (mesma do modelo de chat) e compute_type único — sem
        # fallback automático para CPU/quantização diferente por VRAM
        # disponível em runtime (ver docs/ARCHITECTURE.md §7).
        device: str = "cuda",
        compute_type: str = "int8_float16",
    ) -> None:
        self._model_size = model_size
        self._device = device
        self._compute_type = compute_type
        self._model: WhisperModel | None = None

    def _load_model(self) -> WhisperModel:
        if self._model is None:
            try:
                self._model = WhisperModel(
                    self._model_size,
                    device=self._device,
                    compute_type=self._compute_type,
                )
            except Exception as exc:
                raise SttIndisponivelError(str(exc)) from exc
        return self._model

    async def transcribe(self, audio_bytes: bytes) -> str:
        """Transcreve `audio_bytes` (ex.: wav, mp3) para texto em português.

        # MVP: sem detecção robusta de áudio ruidoso/silencioso, sem VAD e
        # sem streaming — transcrição síncrona de um arquivo curto por vez
        # (ver docs/ARCHITECTURE.md §5).
        """
        try:
            return await asyncio.to_thread(self._transcribe_sync, audio_bytes)
        except SttIndisponivelError:
            raise
        except Exception as exc:
            raise SttIndisponivelError(str(exc)) from exc

    def _transcribe_sync(self, audio_bytes: bytes) -> str:
        model = self._load_model()
        # MVP: idioma fixo em português (domínio da empresa fictícia do TCC),
        # sem detecção automática de idioma (ver docs/ARCHITECTURE.md §5).
        segments, _info = model.transcribe(io.BytesIO(audio_bytes), language="pt")
        return " ".join(segment.text.strip() for segment in segments).strip()
