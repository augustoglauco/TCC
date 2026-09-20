"""Embeddings multimodais via CLIP ViT-B/32 (R6) — imagem e texto no mesmo
espaço vetorial, permitindo busca por similaridade visual no catálogo.

Usa `sentence-transformers` com o modelo `clip-ViT-B-32` (512 dims),
já disponível como dependência do projeto — sem dependência nova.

# MVP: modelo fixo (clip-ViT-B-32), carga lazy, sem seleção dinâmica por
# collection (ver docs/ARCHITECTURE.md §5).
"""

import asyncio
import io
import threading

from sentence_transformers import SentenceTransformer

CLIP_MODEL_NAME = "clip-ViT-B-32"
CLIP_VECTOR_DIMENSION = 512


class InvalidImageError(Exception):
    """Bytes fornecidos não são uma imagem decodificável pelo PIL.

    Erro de entrada (não de infraestrutura) — o chamador deve mapear para um
    400, não para 503. Evita que um `UnidentifiedImageError` cru do PIL
    escape sem tratamento (ver bug 2026-09-20: imagem-lixo no fluxo de
    identificação travava o chat silenciosamente).
    """


class ClipEmbedder:
    """Wrapper fino sobre CLIP via sentence-transformers, com carga lazy.

    Mesmo padrão de `TextEmbedder`: inferência síncrona rodada em thread
    separada para não bloquear o event loop.
    """

    def __init__(self, model_name: str = CLIP_MODEL_NAME) -> None:
        self._model_name = model_name
        self._model: SentenceTransformer | None = None
        self._load_lock = threading.Lock()

    def _load_model(self) -> SentenceTransformer:
        if self._model is None:
            with self._load_lock:
                if self._model is None:
                    self._model = SentenceTransformer(self._model_name)
        return self._model

    def _embed_images_sync(self, images_bytes: list[bytes]) -> list[list[float]]:
        from PIL import Image, UnidentifiedImageError

        # Decodifica ANTES de carregar o modelo: bytes inválidos falham cedo
        # (sem custo de carregar o CLIP) com um erro tipado de entrada, em vez
        # de deixar o `UnidentifiedImageError` cru do PIL escapar. Defesa em
        # profundidade caso um chamador esqueça `detect_image_format` antes
        # (ver bug 2026-09-20).
        try:
            pil_images = [Image.open(io.BytesIO(b)).convert("RGB") for b in images_bytes]
        except (UnidentifiedImageError, OSError) as exc:
            raise InvalidImageError(str(exc)) from exc
        model = self._load_model()
        vectors = model.encode(pil_images, convert_to_numpy=True)
        return [v.tolist() for v in vectors]

    def _embed_texts_sync(self, texts: list[str]) -> list[list[float]]:
        model = self._load_model()
        vectors = model.encode(texts, convert_to_numpy=True)
        return [v.tolist() for v in vectors]

    async def embed_images(self, images_bytes: list[bytes]) -> list[list[float]]:
        """Gera um embedding CLIP por imagem (bytes PNG/JPG/WEBP)."""
        if not images_bytes:
            return []
        return await asyncio.to_thread(self._embed_images_sync, images_bytes)

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Gera um embedding CLIP por texto (mesmo espaço vetorial das imagens)."""
        if not texts:
            return []
        return await asyncio.to_thread(self._embed_texts_sync, texts)
