from app.rag.embeddings import TextEmbedder


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
