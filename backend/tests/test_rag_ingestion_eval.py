"""Testes do harness de otimização de ingestão do RAG (Etapas 0 e 1, Fase 10).

Cobre a mecânica que não depende de infraestrutura: as métricas de
recuperação (funções puras), a conversão de HTML para Markdown, a seleção
de arquivos a partir da auditoria e a integridade do conjunto mínimo. A
rodada real da Etapa 1 exige Qdrant e Postgres no ar e não é testável aqui —
ver `eval/rag_ingestion/README.md`.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

EVAL_DIR = Path(__file__).resolve().parents[1] / "eval"
PASTA = EVAL_DIR / "rag_ingestion"


def _carregar(nome: str):
    # Os scripts vivem em `eval/`, fora do pacote `app` instalado no venv, e
    # importam módulos irmãos (`metricas`) por sys.path — mesmo padrão de
    # `tests/test_model_benchmark.py`.
    sys.path.insert(0, str(PASTA))
    spec = importlib.util.spec_from_file_location(nome, PASTA / f"{nome}.py")
    modulo = importlib.util.module_from_spec(spec)
    # Registrar em `sys.modules` ANTES de executar não é opcional aqui: o
    # `@dataclass` do Python 3.14 resolve as anotações procurando o módulo
    # da classe em `sys.modules` (`dataclasses._is_type`), e sem isso o
    # import de `metricas` falha com AttributeError em vez de carregar.
    sys.modules[nome] = modulo
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def metricas():
    return _carregar("metricas")


@pytest.fixture(scope="module")
def preparar():
    return _carregar("preparar_corpus")


# --------------------------------------------------------------------------
# Métricas de recuperação
# --------------------------------------------------------------------------


def test_deduplicar_com_score_mantem_melhor_score(metricas):
    """Vários chunks do mesmo PDF viram uma entrada, na melhor posição, com
    o score dela.

    Sem a deduplicação, um PDF nas posições 1, 2 e 3 contaria três vezes e
    inflaria o nDCG — a relevância do gabarito é por documento, não por
    chunk. E os pares saem alinhados, que é do que a varredura offline da
    Etapa 4 depende.
    """
    pares = [("a.pdf", 0.9), ("a.pdf", 0.7), ("b.pdf", 0.6), ("a.pdf", 0.5)]
    assert metricas.deduplicar_com_score(pares) == [("a.pdf", 0.9), ("b.pdf", 0.6)]


def test_deduplicar_com_score_vazio(metricas):
    assert metricas.deduplicar_com_score([]) == []


def test_aplicar_threshold_corta_por_score(metricas):
    pares = [("a.pdf", 0.9), ("b.pdf", 0.6), ("c.pdf", 0.3)]
    assert metricas.aplicar_threshold(pares, 0.5) == ["a.pdf", "b.pdf"]
    assert metricas.aplicar_threshold(pares, 0.95) == []
    assert metricas.aplicar_threshold(pares, 0.0) == ["a.pdf", "b.pdf", "c.pdf"]


def test_aplicar_threshold_respeita_top_k(metricas):
    pares = [("a.pdf", 0.9), ("b.pdf", 0.8), ("c.pdf", 0.7)]
    assert metricas.aplicar_threshold(pares, 0.0, top_k=2) == ["a.pdf", "b.pdf"]


def test_aplicar_threshold_no_limite_inclui(metricas):
    """`>=`, não `>`: um documento exatamente no threshold entra, igual ao
    `score_threshold` do Qdrant."""
    assert metricas.aplicar_threshold([("a.pdf", 0.35)], 0.35) == ["a.pdf"]


@pytest.mark.parametrize(
    ("recuperadas", "k", "esperado"),
    [
        (["certo.pdf", "x.pdf"], 1, 1.0),
        (["x.pdf", "certo.pdf"], 1, 0.0),
        (["x.pdf", "certo.pdf"], 3, 1.0),
        (["x.pdf", "y.pdf", "z.pdf", "certo.pdf"], 3, 0.0),
        ([], 5, 0.0),
    ],
)
def test_recall_at_k(metricas, recuperadas, k, esperado):
    assert metricas.recall_at_k(recuperadas, {"certo.pdf"}, k) == esperado


def test_recall_at_k_rejeita_caso_negativo(metricas):
    """Caso negativo não tem ranking para medir — tem que falhar alto, não
    devolver 0.0 silenciosamente (0.0 seria lido como 'recuperou errado')."""
    with pytest.raises(ValueError, match="caso negativo"):
        metricas.recall_at_k(["a.pdf"], set(), 5)


def test_recall_at_k_rejeita_k_invalido(metricas):
    with pytest.raises(ValueError, match="k deve ser positivo"):
        metricas.recall_at_k(["a.pdf"], {"a.pdf"}, 0)


@pytest.mark.parametrize(
    ("recuperadas", "esperado"),
    [(["certo.pdf"], 1.0), (["x.pdf", "certo.pdf"], 0.5), (["x.pdf", "y.pdf"], 0.0), ([], 0.0)],
)
def test_reciprocal_rank(metricas, recuperadas, esperado):
    assert metricas.reciprocal_rank(recuperadas, {"certo.pdf"}) == esperado


def test_ndcg_fonte_unica_no_topo_vale_1(metricas):
    assert metricas.ndcg_at_k(["certo.pdf", "x.pdf"], {"certo.pdf"}, 10) == 1.0


def test_ndcg_decai_com_a_posicao(metricas):
    """nDCG cai monotonicamente conforme o acerto desce no ranking."""
    valores = [
        metricas.ndcg_at_k(["x.pdf"] * i + ["certo.pdf"], {"certo.pdf"}, 10) for i in range(4)
    ]
    assert valores == sorted(valores, reverse=True)
    assert valores[0] == 1.0
    assert all(0 < v < 1 for v in valores[1:])


def test_ndcg_fora_do_corte_vale_zero(metricas):
    assert metricas.ndcg_at_k(["x.pdf"] * 10 + ["certo.pdf"], {"certo.pdf"}, 10) == 0.0


def test_ndcg_multiplas_fontes_aceitas_no_topo_vale_1(metricas):
    """Com duas fontes aceitas, o IDCG considera as duas — o ranking ideal
    tem as duas no topo, e só aí o nDCG vale 1,0."""
    assert metricas.ndcg_at_k(["a.pdf", "b.pdf"], {"a.pdf", "b.pdf"}, 10) == 1.0
    parcial = metricas.ndcg_at_k(["a.pdf", "x.pdf"], {"a.pdf", "b.pdf"}, 10)
    assert 0 < parcial < 1


def test_avaliar_conjunto_separa_positivas_de_negativas(metricas):
    resultados = [
        metricas.ResultadoPergunta("p1", False, ["certo.pdf"], {"certo.pdf"}),
        metricas.ResultadoPergunta("p2", False, ["x.pdf"], {"certo.pdf"}),
        metricas.ResultadoPergunta("n1", True, [], set()),
        metricas.ResultadoPergunta("n2", True, ["qualquer.pdf"], set()),
    ]
    agregado = metricas.avaliar_conjunto(resultados)

    assert agregado["n_total"] == 4
    assert agregado["n_positivas"] == 2
    assert agregado["n_negativas"] == 2
    assert agregado["recall"]["@5"] == 0.5
    assert agregado["mrr"] == 0.5
    # n1 acertou (devolveu vazio), n2 errou (devolveu algo) → 50%.
    assert agregado["acerto_negativas"] == 0.5
    assert agregado["taxa_vazio_positivas"] == 0.0


def test_avaliar_conjunto_sem_negativas_devolve_none(metricas):
    """Métrica sem amostra é `None`, não 0.0 — 0.0 pareceria falha total."""
    resultados = [metricas.ResultadoPergunta("p1", False, ["certo.pdf"], {"certo.pdf"})]
    agregado = metricas.avaliar_conjunto(resultados)
    assert agregado["acerto_negativas"] is None
    assert agregado["recall"]["@1"] == 1.0


def test_avaliar_conjunto_so_negativas_devolve_none_no_ranking(metricas):
    resultados = [metricas.ResultadoPergunta("n1", True, [], set())]
    agregado = metricas.avaliar_conjunto(resultados)
    assert agregado["ndcg@10"] is None
    assert agregado["mrr"] is None
    assert agregado["acerto_negativas"] == 1.0


def test_taxa_vazio_conta_positiva_sem_resultado(metricas):
    resultados = [
        metricas.ResultadoPergunta("p1", False, [], {"certo.pdf"}),
        metricas.ResultadoPergunta("p2", False, ["certo.pdf"], {"certo.pdf"}),
    ]
    assert metricas.avaliar_conjunto(resultados)["taxa_vazio_positivas"] == 0.5


# --------------------------------------------------------------------------
# Conversão de HTML (Etapa 0 / preparar_corpus)
# --------------------------------------------------------------------------


def test_html_para_markdown_recupera_tags_customizadas(preparar):
    """Regressão da perda de 93% do conteúdo.

    A primeira versão do conversor olhava só tags HTML padrão, e o doc de
    API do REP iDClass guarda o texto em `<description>`, `<name>`, `<type>`
    e `<code>` — resultado: 4 mil dos 57 mil caracteres, sem nenhum erro.
    """
    html = """
    <html><body>
      <div class="param">
        <name>login</name><type>string</type>
        <description>Usuario administrador do equipamento.</description>
      </div>
      <code>POST /login.fcgi</code>
    </body></html>
    """
    md = preparar.html_para_markdown(html)
    assert "login" in md
    assert "Usuario administrador do equipamento." in md
    assert "POST /login.fcgi" in md


def test_html_para_markdown_nao_duplica_texto_de_bloco_aninhado(preparar):
    """Só blocos-folha são emitidos: um `<div>` que embala `<p>` não repete
    o texto dos filhos."""
    md = preparar.html_para_markdown("<div><p>unico</p></div>")
    assert md.count("unico") == 1


def test_html_para_markdown_descarta_script_e_style(preparar):
    md = preparar.html_para_markdown(
        "<html><head><style>.a{color:red}</style></head>"
        "<body><script>var x=1;</script><p>visivel</p></body></html>"
    )
    assert "visivel" in md
    assert "color:red" not in md
    assert "var x=1" not in md


def test_html_para_markdown_mapeia_titulos_e_listas(preparar):
    md = preparar.html_para_markdown("<h2>Titulo</h2><ul><li>item a</li><li>item b</li></ul>")
    assert "## Titulo" in md
    assert "- item a" in md
    assert "- item b" in md


def test_html_para_markdown_vazio(preparar):
    assert preparar.html_para_markdown("<html><body></body></html>").strip() == ""


def test_limiar_de_recuperacao_e_exigente(preparar):
    """O limiar existe para barrar exatamente a perda silenciosa de 93%."""
    assert 0.5 < preparar.LIMIAR_RECUPERACAO_HTML <= 1.0


# --------------------------------------------------------------------------
# Varredura offline de threshold (Etapa 4)
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def varrer():
    return _carregar("varrer_threshold")


def _item(id_: str, negativa: bool, pares, aceitas):
    return {
        "id": id_,
        "negativa": negativa,
        "fontes_aceitas": aceitas,
        "recuperadas": [{"fonte": f, "score": s} for f, s in pares],
        "score_maximo": pares[0][1] if pares else None,
    }


def test_separabilidade_detecta_conjunto_separavel(varrer):
    itens = [
        _item("p1", False, [("certo.pdf", 0.80)], ["certo.pdf"]),
        _item("n1", True, [("x.pdf", 0.40)], []),
    ]
    sep = varrer.separabilidade(itens)
    assert sep["separavel"] is True
    assert sep["positivas_abaixo_da_pior_negativa"] == 0


def test_separabilidade_detecta_sobreposicao(varrer):
    """O caso real do baseline: positivas pontuando abaixo da pior negativa,
    o que torna qualquer `score_threshold` incapaz de separar."""
    itens = [
        _item("p1", False, [("certo.pdf", 0.45)], ["certo.pdf"]),
        _item("p2", False, [("certo.pdf", 0.80)], ["certo.pdf"]),
        _item("n1", True, [("x.pdf", 0.61)], []),
    ]
    sep = varrer.separabilidade(itens)
    assert sep["separavel"] is False
    assert sep["positivas_abaixo_da_pior_negativa"] == 1
    assert sep["n_positivas"] == 2


def test_separabilidade_sem_negativas_nao_opina(varrer):
    sep = varrer.separabilidade([_item("p1", False, [("a.pdf", 0.5)], ["a.pdf"])])
    assert sep["separavel"] is None


def test_varrer_devolve_uma_linha_por_combinacao(varrer):
    itens = [
        _item("p1", False, [("certo.pdf", 0.70), ("x.pdf", 0.50)], ["certo.pdf"]),
        _item("n1", True, [("y.pdf", 0.60)], []),
    ]
    linhas = varrer.varrer(itens)
    assert len(linhas) == len(varrer.TOP_KS) * len(varrer.THRESHOLDS)
    assert {linha["top_k"] for linha in linhas} == set(varrer.TOP_KS)


def test_varrer_threshold_alto_zera_recall_e_acerta_negativas(varrer):
    """Monotonia esperada: subir o threshold troca recuperação por silêncio."""
    itens = [
        _item("p1", False, [("certo.pdf", 0.50)], ["certo.pdf"]),
        _item("n1", True, [("y.pdf", 0.40)], []),
    ]
    linhas = {(x["top_k"], x["score_threshold"]): x for x in varrer.varrer(itens)}
    baixo = linhas[(5, 0.0)]
    meio = linhas[(5, 0.45)]
    alto = linhas[(5, 0.75)]

    # thr=0.0: recupera tudo, inclusive na negativa -> erra a negativa.
    assert baixo["recall@5"] == 1.0
    assert baixo["acerto_negativas"] == 0.0
    # thr=0.45 fica entre os dois scores (negativa 0.40 < 0.45 <= 0.50
    # positiva): acerta as duas. É o conjunto separável.
    assert meio["recall@5"] == 1.0
    assert meio["acerto_negativas"] == 1.0
    # thr=0.75: corta tudo -> silêncio total, acerta a negativa por omissão.
    assert alto["recall@5"] == 0.0
    assert alto["taxa_vazio_positivas"] == 1.0
    assert alto["acerto_negativas"] == 1.0


def test_varredura_recusa_base_com_threshold_alto(varrer, tmp_path):
    """Varrer sobre uma base já cortada produziria tabela truncada em
    silêncio — o script tem que recusar."""
    base = tmp_path / "resultados_etapa1.json"
    base.write_text(
        json.dumps(
            {
                "config": {"score_threshold": 0.35, "embedding_model": "qualquer"},
                "itens": [_item("p1", False, [("a.pdf", 0.9)], ["a.pdf"])],
            }
        ),
        encoding="utf-8",
    )
    assert varrer.main(["varrer_threshold.py", "--entrada", str(base)]) == 1


# --------------------------------------------------------------------------
# Integridade do conjunto mínimo
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def dataset():
    return json.loads((PASTA / "dataset_minimo.json").read_text(encoding="utf-8"))


def test_dataset_tem_positivas_e_negativas(dataset):
    """Sem caso negativo não se mede alucinação; sem positivo não se mede
    recuperação. Mesma garantia do dataset de visão (Fase 10)."""
    perguntas = dataset["perguntas"]
    positivas = [p for p in perguntas if p["fontes_aceitas"]]
    negativas = [p for p in perguntas if not p["fontes_aceitas"]]
    assert positivas, "conjunto sem pergunta positiva"
    assert negativas, "conjunto sem pergunta negativa"
    assert len(negativas) >= 3


def test_dataset_ids_unicos(dataset):
    ids = [p["id"] for p in dataset["perguntas"]]
    assert len(ids) == len(set(ids))


def test_dataset_positivas_tem_trecho_de_gabarito(dataset):
    """O trecho ao lado da pergunta é o que faz a revisão humana custar ~10 s
    em vez de ~1,5 min por item (`docs/EVALUATION.md` Seção 0)."""
    for p in dataset["perguntas"]:
        if p["fontes_aceitas"]:
            assert p.get("trecho"), f"{p['id']} sem trecho de gabarito"
            assert p.get("resposta_esperada")


def test_dataset_nao_usa_changelog_como_fonte(dataset):
    """`ingest_file` grava só o basename em `source`, e `changelog_pt-br.pdf`
    existe em iDFace E em iDAccess Pro — seria gabarito ambíguo."""
    for p in dataset["perguntas"]:
        for fonte in p["fontes_aceitas"]:
            assert "changelog" not in fonte.lower(), f"{p['id']} usa changelog como fonte"


def test_dataset_fontes_existem_no_corpus(dataset):
    """Protege contra o erro que tirou Q8/Q19 do conjunto antigo: gabarito
    apontando para arquivo que não está no corpus."""
    corpus = Path(__file__).resolve().parents[2] / "docs" / "Manuais_fornecedor" / "ControlId"
    if not corpus.is_dir():
        pytest.skip("corpus não disponível neste ambiente")
    existentes = {c.name for c in corpus.rglob("*") if c.is_file()}
    for p in dataset["perguntas"]:
        for fonte in p["fontes_aceitas"]:
            assert fonte in existentes, f"{p['id']}: {fonte} não existe no corpus"


def test_dataset_fontes_ficam_nas_pastas_declaradas(dataset):
    """Cada fonte do gabarito tem de viver numa das pastas que o harness
    ingere — senão a pergunta é insolúvel por construção."""
    corpus = Path(__file__).resolve().parents[2] / "docs" / "Manuais_fornecedor" / "ControlId"
    if not corpus.is_dir():
        pytest.skip("corpus não disponível neste ambiente")
    permitidos: set[str] = set()
    for pasta in dataset["_pastas"]:
        permitidos |= {c.name for c in (corpus / pasta).rglob("*") if c.is_file()}
    for p in dataset["perguntas"]:
        for fonte in p["fontes_aceitas"]:
            assert fonte in permitidos, (
                f"{p['id']}: {fonte} fora das pastas de {dataset['_pastas']}"
            )


# --------------------------------------------------------------------------
# Script de ingestão do corpus de avaliação (ingerir_corpus_avaliacao.py)
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def ingerir_corpus():
    caminho = Path(__file__).resolve().parents[1] / "scripts" / "ingerir_corpus_avaliacao.py"
    spec = importlib.util.spec_from_file_location("ingerir_corpus_avaliacao", caminho)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["ingerir_corpus_avaliacao"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def test_corpus_padrao_aponta_para_controlid(ingerir_corpus):
    """O corpus decidido na Etapa 0 (2026-10-17) é `ControlId/`, não a pasta
    `Manuais_fornecedor` inteira (que inclui `catalago/` e o catálogo da raiz)."""
    assert ingerir_corpus.CORPUS_PADRAO.name == "ControlId"
    assert ingerir_corpus.CORPUS_PADRAO.parent.name == "Manuais_fornecedor"


def test_listar_arquivos_corpus_inclui_pdf_md_txt_e_exclui_html_tif(ingerir_corpus, tmp_path):
    """Depois da conversão do `.html` para `.md` na Etapa 0, o script de
    ingestão deve coletar todas as extensões aceitas por `SUPPORTED_SUFFIXES`
    (`.pdf`, `.md`, `.txt`) e ignorar `.html`/`.tif`/`.jpg`."""
    (tmp_path / "manual.pdf").write_bytes(b"%PDF-1.4")
    (tmp_path / "api_idclass_latest.md").write_text("# API", encoding="utf-8")
    (tmp_path / "notas.txt").write_text("texto", encoding="utf-8")
    (tmp_path / "api_idclass_latest.html").write_text("<html></html>", encoding="utf-8")
    (tmp_path / "foto.tif").write_bytes(b"II*")

    encontrados = [p.name for p in ingerir_corpus.listar_arquivos_corpus(tmp_path)]
    assert encontrados == ["api_idclass_latest.md", "manual.pdf", "notas.txt"]


# --------------------------------------------------------------------------
# Etapa 2 — comparação de modelos de embedding (run_etapa2.py)
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def etapa2():
    return _carregar("run_etapa2")


def test_candidatos_etapa2_cobrem_quatro_modelos_do_plano(etapa2):
    """Os 4 modelos previstos em `docs/EVALUATION.md` Seção 2.1 (Etapa 2)
    precisam estar declarados na ordem canônica."""
    modelos = [c.embedding_model for c in etapa2.CANDIDATOS_ETAPA2]
    assert modelos == [
        "paraphrase-multilingual-MiniLM-L12-v2",
        "google/embeddinggemma-300m",
        "intfloat/multilingual-e5-large-instruct",
        "BAAI/bge-m3",
    ]


def test_candidatos_etapa2_respeitam_janela_de_tokens(etapa2):
    """Regra da Etapa 2 (`docs/EVALUATION.md:556-559`): cada modelo tem de ser
    medido com um `chunk_size` que caiba na sua janela (`MiniLM` truncava ~45%
    de cada chunk de 800 chars na janela de 128 tokens)."""
    for c in etapa2.CANDIDATOS_ETAPA2:
        tokens_estimados = c.chunk_size / 3.5
        assert tokens_estimados <= c.janela_tokens, (
            f"{c.id}: chunk_size={c.chunk_size} (~{tokens_estimados:.0f} tokens) "
            f"excede janela de {c.janela_tokens} tokens"
        )
        assert c.chunk_size > c.chunk_overlap > 0


def test_filtrar_candidatos_seleciona_subconjunto_ou_falha_em_id_invalido(etapa2):
    todos = etapa2.filtrar_candidatos(None)
    assert len(todos) == 4

    apenas_gemma = etapa2.filtrar_candidatos(["embeddinggemma-300m"])
    assert [c.id for c in apenas_gemma] == ["embeddinggemma-300m"]

    with pytest.raises(ValueError, match="Candidato desconhecido"):
        etapa2.filtrar_candidatos(["modelo-inexistente"])


def test_ranquear_candidatos_ordena_por_ndcg_recall_mrr_e_separabilidade(etapa2):
    entradas = [
        {
            "id": "minilm-l12-v2",
            "embedding_model": "paraphrase-multilingual-MiniLM-L12-v2",
            "metricas_sem_corte": {
                "ndcg@10": 0.386,
                "recall": {"@5": 0.500},
                "mrr": 0.347,
            },
            "separabilidade": {"separavel": False},
            "tempo_ingestao_s": 4.2,
        },
        {
            "id": "bge-m3",
            "embedding_model": "BAAI/bge-m3",
            "metricas_sem_corte": {
                "ndcg@10": 0.780,
                "recall": {"@5": 0.833},
                "mrr": 0.750,
            },
            "separabilidade": {"separavel": True},
            "tempo_ingestao_s": 14.0,
        },
        {
            "id": "embeddinggemma-300m",
            "embedding_model": "google/embeddinggemma-300m",
            "metricas_sem_corte": {
                "ndcg@10": 0.780,
                "recall": {"@5": 0.833},
                "mrr": 0.750,
            },
            "separabilidade": {"separavel": True},
            "tempo_ingestao_s": 9.5,
        },
    ]
    ranking = etapa2.ranquear_candidatos(entradas)
    assert [r["id"] for r in ranking] == [
        "embeddinggemma-300m",
        "bge-m3",
        "minilm-l12-v2",
    ]
    assert [r["posicao"] for r in ranking] == [1, 2, 3]
