"""Embeddings de texto para o RAG (R4) via sentence-transformers.

# MVP: um único modelo de embeddings fixo por config, carregado sob demanda
# (lazy singleton), sem seleção dinâmica por idioma/domínio nem cache em
# disco além do cache padrão do Hugging Face (ver docs/ARCHITECTURE.md §5).
"""

import asyncio
import threading

from sentence_transformers import SentenceTransformer

# Modelo multilíngue leve (~384 dims) — cobre português sem exigir um modelo
# maior, conforme docs/TECHNOLOGY_STACK.md ("Embeddings (texto)").
DEFAULT_EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"


class TextEmbedder:
    """Wrapper fino sobre `sentence-transformers`, com carga lazy do modelo.

    A inferência do modelo é síncrona/bloqueante (CPU ou GPU) — os métodos
    públicos rodam em thread separada (`asyncio.to_thread`) para não travar
    o event loop, seguindo o mesmo padrão de `app.stt.whisper_client`.
    """

    def __init__(self, model_name: str = DEFAULT_EMBEDDING_MODEL) -> None:
        self._model_name = model_name
        self._model: SentenceTransformer | None = None
        # `_load_model` roda em thread de worker (`asyncio.to_thread`), não
        # numa coroutine — `threading.Lock` (não `asyncio.Lock`) é o
        # primitivo certo para serializar chamadas concorrentes vindas de
        # requisições HTTP simultâneas. Sem isso, duas buscas chegando antes
        # do primeiro carregamento terminar carregavam o modelo em
        # duplicidade (VRAM em dobro por um instante — risco já documentado
        # em docs/ARCHITECTURE.md §7).
        self._load_lock = threading.Lock()

    @property
    def model_name(self) -> str:
        return self._model_name

    def _load_model(self) -> SentenceTransformer:
        if self._model is None:
            with self._load_lock:
                if self._model is None:  # dupla checagem: outra thread pode ter carregado
                    self._model = SentenceTransformer(self._model_name)
        return self._model

    def _embed_sync(self, texts: list[str]) -> list[list[float]]:
        model = self._load_model()
        vectors = model.encode(texts, convert_to_numpy=True)
        return [vector.tolist() for vector in vectors]

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Gera um embedding por texto de `texts`, na mesma ordem de entrada."""
        if not texts:
            return []
        return await asyncio.to_thread(self._embed_sync, texts)

    def _get_dimension_sync(self) -> int:
        model = self._load_model()
        # `get_embedding_dimension` é o nome atual do método (renomeado numa
        # versão recente do sentence-transformers); `get_sentence_embedding_
        # dimension` é o nome antigo, mantido como alias depreciado nas
        # versões novas mas o único que existe nas mais antigas —
        # `pyproject.toml` fixa só `>=3.0`, sem teto, então uma instalação
        # antiga não tem o nome novo. `getattr` com default avalia o default
        # antes de checar o atributo, então usa `None` como sentinela em vez
        # de `model.get_sentence_embedding_dimension` direto (isso quebraria
        # numa instalação/dublê que só tenha o nome novo).
        get_dimension = getattr(model, "get_embedding_dimension", None)
        if get_dimension is None:
            get_dimension = model.get_sentence_embedding_dimension
        return get_dimension()

    async def get_dimension(self) -> int:
        """Dimensão dos vetores gerados pelo modelo carregado."""
        return await asyncio.to_thread(self._get_dimension_sync)
