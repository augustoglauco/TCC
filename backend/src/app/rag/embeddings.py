"""Embeddings de texto para o RAG (R4) via sentence-transformers.

# MVP: um único modelo de embeddings por collection, carregado sob demanda
# (lazy singleton via `EmbedderRegistry`), sem seleção dinâmica por idioma/
# domínio nem cache em disco além do cache padrão do Hugging Face (ver
# docs/ARCHITECTURE.md §5). Prefixos assimétricos de tarefa (consulta vs.
# documento) são aplicados aqui por família de modelo (decisão de 2026-10-17,
# Etapa 2 da otimização do RAG — ver docs/Manuais/PROMPTS_E_INSTRUCOES_LLM.md).
"""

import asyncio
import logging
import threading

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Modelo multilíngue leve (~384 dims) — baseline inicial do MVP (ver
# docs/CONVENTIONS.md, "Bibliotecas e versões em uso" e docs/EVALUATION.md §2.1).
DEFAULT_EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

# Prefixos assimétricos de tarefa exigidos pelos candidatos da Etapa 2
# (docs/ARCHITECTURE.md, decisão de 2026-10-17; catalogados em
# docs/Manuais/PROMPTS_E_INSTRUCOES_LLM.md, regra 11 do CLAUDE.md):
EMBEDDINGGEMMA_QUERY_PREFIX = "task: search result | query: "
EMBEDDINGGEMMA_DOCUMENT_PREFIX = "title: none | text: "
E5_QUERY_PREFIX = "query: "
E5_DOCUMENT_PREFIX = "passage: "

# `google/embeddinggemma-300m` é um repositório gated no Hugging Face (exige
# `HF_TOKEN` com aceite manual dos termos). Quando o ambiente não tem token
# configurado, `SentenceTransformer` levanta `OSError` (`GatedRepoError`);
# caímos automaticamente para o espelho aberto com os mesmos pesos e
# tokenizer (`unsloth/embeddinggemma-300m`), mantendo `model_name` canônico.
_FALLBACK_MIRRORS: dict[str, str] = {
    "google/embeddinggemma-300m": "unsloth/embeddinggemma-300m",
}


def prefixos_do_modelo(model_name: str) -> tuple[str, str]:
    """Devolve `(prefixo_consulta, prefixo_documento)` exigidos por `model_name`.

    Modelos simétricos (ex.: `paraphrase-multilingual-MiniLM-L12-v2`,
    `BAAI/bge-m3`) recebem `("", "")`.
    """
    nome = model_name.lower()
    if "embeddinggemma" in nome:
        return (EMBEDDINGGEMMA_QUERY_PREFIX, EMBEDDINGGEMMA_DOCUMENT_PREFIX)
    if "e5-" in nome:
        return (E5_QUERY_PREFIX, E5_DOCUMENT_PREFIX)
    return ("", "")


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
                    try:
                        self._model = SentenceTransformer(self._model_name)
                    except OSError:
                        mirror = _FALLBACK_MIRRORS.get(self._model_name)
                        if mirror is None:
                            raise
                        logger.warning(
                            "rag_embedding_fallback_mirror modelo=%s mirror=%s",
                            self._model_name,
                            mirror,
                        )
                        self._model = SentenceTransformer(mirror)
        return self._model

    def _format_texts(self, texts: list[str], *, is_query: bool) -> list[str]:
        query_prefix, doc_prefix = prefixos_do_modelo(self._model_name)
        prefix = query_prefix if is_query else doc_prefix
        if not prefix:
            return texts
        return [f"{prefix}{t}" for t in texts]

    def _embed_sync(self, texts: list[str], *, is_query: bool = False) -> list[list[float]]:
        model = self._load_model()
        formatted = self._format_texts(texts, is_query=is_query)
        vectors = model.encode(formatted, convert_to_numpy=True)
        return [vector.tolist() for vector in vectors]

    async def embed(self, texts: list[str], *, is_query: bool = False) -> list[list[float]]:
        """Gera um embedding por texto de `texts`, na mesma ordem de entrada.

        Quando o modelo exige prefixos assimétricos de tarefa (ex.:
        `embeddinggemma` ou `multilingual-e5`), antepõe o prefixo de consulta
        (`is_query=True`) ou de documento (`is_query=False`, padrão).
        """
        if not texts:
            return []
        return await asyncio.to_thread(self._embed_sync, texts, is_query=is_query)

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
