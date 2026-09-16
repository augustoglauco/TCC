"""Cache de instâncias de `TextEmbedder` por nome de modelo (Entregas B+C+D,
além do MVP) — evita recarregar/duplicar o mesmo modelo em VRAM quando
várias collections compartilham o mesmo `embedding_model` (ver
docs/superpowers/specs/2026-09-15-rag-collections-config-design.md §5).
"""

import threading

from app.rag.embeddings import TextEmbedder


class EmbedderRegistry:
    def __init__(self) -> None:
        self._embedders: dict[str, TextEmbedder] = {}
        self._lock = threading.Lock()

    def get(self, model_name: str) -> TextEmbedder:
        with self._lock:
            embedder = self._embedders.get(model_name)
            if embedder is None:
                embedder = TextEmbedder(model_name)
                self._embedders[model_name] = embedder
            return embedder
