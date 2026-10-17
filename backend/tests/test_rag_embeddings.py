import numpy as np
import pytest

import app.rag.embeddings as embeddings_mod
from app.rag.embeddings import (
    E5_DOCUMENT_PREFIX,
    E5_QUERY_PREFIX,
    EMBEDDINGGEMMA_DOCUMENT_PREFIX,
    EMBEDDINGGEMMA_QUERY_PREFIX,
    TextEmbedder,
    prefixos_do_modelo,
)


class _ModeloComNomeAtual:
    """Simula uma instalação recente do sentence-transformers (nome novo)."""

    def get_embedding_dimension(self) -> int:
        return 384


class _ModeloComNomeAntigo:
    """Simula uma instalação antiga do sentence-transformers — só tem o
    método com o nome anterior ao rename (`pyproject.toml` fixa só
    `>=3.0`, sem teto, então essa versão é possível numa instalação nova)."""

    def get_sentence_embedding_dimension(self) -> int:
        return 384


class _ModeloGravador:
    """Registra os textos exatos entregues a `encode` para verificar prefixos."""

    def __init__(self) -> None:
        self.recebidos: list[list[str]] = []

    def encode(self, texts: list[str], convert_to_numpy: bool = True):
        self.recebidos.append(list(texts))
        return np.ones((len(texts), 4), dtype=np.float32)


async def test_get_dimension_usa_nome_atual_do_metodo_quando_disponivel():
    embedder = TextEmbedder()
    embedder._model = _ModeloComNomeAtual()  # bypassa o load real do modelo

    assert await embedder.get_dimension() == 384


async def test_get_dimension_cai_para_nome_antigo_em_instalacao_desatualizada():
    embedder = TextEmbedder()
    embedder._model = _ModeloComNomeAntigo()

    assert await embedder.get_dimension() == 384


def test_model_name_expoe_o_nome_do_modelo_configurado():
    embedder = TextEmbedder("modelo-de-teste")

    assert embedder.model_name == "modelo-de-teste"


@pytest.mark.parametrize(
    ("model_name", "esperado_query", "esperado_doc"),
    [
        (
            "google/embeddinggemma-300m",
            EMBEDDINGGEMMA_QUERY_PREFIX,
            EMBEDDINGGEMMA_DOCUMENT_PREFIX,
        ),
        (
            "unsloth/embeddinggemma-300m",
            EMBEDDINGGEMMA_QUERY_PREFIX,
            EMBEDDINGGEMMA_DOCUMENT_PREFIX,
        ),
        (
            "intfloat/multilingual-e5-large-instruct",
            E5_QUERY_PREFIX,
            E5_DOCUMENT_PREFIX,
        ),
        ("paraphrase-multilingual-MiniLM-L12-v2", "", ""),
        ("BAAI/bge-m3", "", ""),
    ],
)
def test_prefixos_do_modelo_por_familia(model_name, esperado_query, esperado_doc):
    assert prefixos_do_modelo(model_name) == (esperado_query, esperado_doc)


async def test_embed_embeddinggemma_aplica_prefixo_de_documento_e_de_consulta():
    embedder = TextEmbedder("google/embeddinggemma-300m")
    gravador = _ModeloGravador()
    embedder._model = gravador

    await embedder.embed(["manual do iDFace", "datasheet iDBox"])
    await embedder.embed(["qual a capacidade do iDFace?"], is_query=True)

    assert gravador.recebidos[0] == [
        "title: none | text: manual do iDFace",
        "title: none | text: datasheet iDBox",
    ]
    assert gravador.recebidos[1] == [
        "task: search result | query: qual a capacidade do iDFace?",
    ]


async def test_embed_e5_aplica_prefixo_passage_e_query():
    embedder = TextEmbedder("intfloat/multilingual-e5-large-instruct")
    gravador = _ModeloGravador()
    embedder._model = gravador

    await embedder.embed(["trecho do documento"])
    await embedder.embed(["pergunta do usuário"], is_query=True)

    assert gravador.recebidos[0] == ["passage: trecho do documento"]
    assert gravador.recebidos[1] == ["query: pergunta do usuário"]


async def test_embed_modelo_sem_prefixo_preserva_texto_intacto():
    embedder = TextEmbedder("BAAI/bge-m3")
    gravador = _ModeloGravador()
    embedder._model = gravador

    await embedder.embed(["trecho original"])
    await embedder.embed(["pergunta original"], is_query=True)

    assert gravador.recebidos == [["trecho original"], ["pergunta original"]]


def test_load_model_usa_espelho_aberto_quando_repo_oficial_e_gated(monkeypatch):
    chamadas: list[str] = []

    def _fake_sentence_transformer(nome: str):
        chamadas.append(nome)
        if nome == "google/embeddinggemma-300m":
            raise OSError("401 Client Error: GatedRepoError")
        return _ModeloComNomeAtual()

    monkeypatch.setattr(embeddings_mod, "SentenceTransformer", _fake_sentence_transformer)
    embedder = TextEmbedder("google/embeddinggemma-300m")

    modelo = embedder._load_model()

    assert isinstance(modelo, _ModeloComNomeAtual)
    assert chamadas == ["google/embeddinggemma-300m", "unsloth/embeddinggemma-300m"]
    assert embedder.model_name == "google/embeddinggemma-300m"
