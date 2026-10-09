"""Testes do roll-up puro do relatório de uso de IA (item E do ledger).

Sem banco e sem HTTP de propósito: a regra sutil deste item é a soma que
respeita `None` (não-medido) versus `0.0` (grátis conhecido), e ela é
testada direto na função, não através do endpoint.
"""

from app.services.ai_usage_report import (
    EventoDiario,
    LinhaAgregada,
    montar_relatorio,
)


def _linha(
    origem="chat",
    ambiente="externo",
    modelo="gpt-x",
    operacao="geracao_resposta",
    chamadas=1,
    tokens_entrada=100,
    tokens_saida=10,
    custo_usd=0.001,
    chamadas_sem_custo_medido=0,
) -> LinhaAgregada:
    return LinhaAgregada(
        origem=origem,
        ambiente=ambiente,
        modelo=modelo,
        operacao=operacao,
        chamadas=chamadas,
        tokens_entrada=tokens_entrada,
        tokens_saida=tokens_saida,
        custo_usd=custo_usd,
        chamadas_sem_custo_medido=chamadas_sem_custo_medido,
    )


def test_relatorio_vazio_nao_inventa_zeros_de_custo():
    rel = montar_relatorio(
        period="7d",
        linhas=[],
        eventos_diarios=[],
        chats_encerrados_total=0,
        chats_encerrados_por_dia={},
    )

    assert rel.period == "7d"
    assert rel.totais.chamadas == 0
    # Nada medido => `None`, não `0.0`: o painel precisa distinguir
    # "não houve chamada" de "houve chamada grátis".
    assert rel.totais.custo_usd is None
    assert rel.totais.tokens_entrada is None
    assert rel.por_origem == []
    assert rel.por_ambiente == []
    assert rel.por_modelo == []
    assert rel.por_operacao == []
    assert rel.diario == []
    assert rel.atendimento.chats_encerrados == 0


def test_totais_fecham_com_a_soma_por_origem():
    linhas = [
        _linha(origem="chat", chamadas=3, tokens_entrada=300, tokens_saida=30, custo_usd=0.003),
        _linha(origem="b2b", chamadas=2, tokens_entrada=200, tokens_saida=20, custo_usd=0.002),
        _linha(origem="admin", chamadas=1, tokens_entrada=100, tokens_saida=10, custo_usd=0.001),
    ]

    rel = montar_relatorio(
        period="30d",
        linhas=linhas,
        eventos_diarios=[],
        chats_encerrados_total=5,
        chats_encerrados_por_dia={},
    )

    assert rel.totais.chamadas == 6
    assert rel.totais.custo_usd == 0.006
    assert rel.totais.tokens_entrada == 600
    assert rel.totais.tokens_saida == 60

    por_origem = {b.origem: b for b in rel.por_origem}
    assert set(por_origem) == {"chat", "b2b", "admin"}
    assert por_origem["chat"].chamadas == 3
    assert sum(b.chamadas for b in rel.por_origem) == rel.totais.chamadas
    assert round(sum(b.custo_usd for b in rel.por_origem), 6) == rel.totais.custo_usd
    assert rel.atendimento.chats_encerrados == 5


def test_custo_todo_nao_medido_sai_none_e_conta_sem_custo_medido():
    linhas = [
        _linha(
            origem="chat",
            ambiente="interno",
            modelo="clip",
            operacao="identificacao_imagem_clip",
            chamadas=4,
            tokens_entrada=None,
            tokens_saida=None,
            custo_usd=None,
            chamadas_sem_custo_medido=4,
        )
    ]

    rel = montar_relatorio(
        period="7d",
        linhas=linhas,
        eventos_diarios=[],
        chats_encerrados_total=0,
        chats_encerrados_por_dia={},
    )

    assert rel.totais.custo_usd is None
    assert rel.totais.tokens_entrada is None
    assert rel.totais.chamadas == 4
    assert rel.totais.chamadas_sem_custo_medido == 4


def test_custo_parcialmente_medido_soma_so_o_medido_e_sinaliza_o_resto():
    linhas = [
        _linha(chamadas=2, custo_usd=0.002, tokens_entrada=200, tokens_saida=20),
        _linha(
            modelo="clip",
            ambiente="interno",
            operacao="identificacao_imagem_clip",
            chamadas=3,
            custo_usd=None,
            tokens_entrada=None,
            tokens_saida=None,
            chamadas_sem_custo_medido=3,
        ),
    ]

    rel = montar_relatorio(
        period="7d",
        linhas=linhas,
        eventos_diarios=[],
        chats_encerrados_total=0,
        chats_encerrados_por_dia={},
    )

    assert rel.totais.chamadas == 5
    assert rel.totais.custo_usd == 0.002
    assert rel.totais.chamadas_sem_custo_medido == 3


def test_custo_zero_conhecido_nao_e_confundido_com_nao_medido():
    linhas = [
        _linha(
            ambiente="interno",
            modelo="llama3.1:8b",
            custo_usd=0.0,
            chamadas=2,
            chamadas_sem_custo_medido=0,
        )
    ]

    rel = montar_relatorio(
        period="7d",
        linhas=linhas,
        eventos_diarios=[],
        chats_encerrados_total=0,
        chats_encerrados_por_dia={},
    )

    assert rel.totais.custo_usd == 0.0
    assert rel.totais.custo_usd is not None
    assert rel.totais.chamadas_sem_custo_medido == 0


def test_agrupamentos_usam_as_chaves_certas():
    linhas = [
        _linha(origem="chat", ambiente="interno", modelo="clip", operacao="identificacao_imagem_clip", custo_usd=0.0),
        _linha(origem="chat", ambiente="externo", modelo="gemma-vision", operacao="identificacao_imagem_visao_externa"),
        _linha(origem="admin", ambiente="externo", modelo="gemma-vision", operacao="extracao_catalogo_visao_externa"),
    ]

    rel = montar_relatorio(
        period="all",
        linhas=linhas,
        eventos_diarios=[],
        chats_encerrados_total=0,
        chats_encerrados_por_dia={},
    )

    assert {b.ambiente for b in rel.por_ambiente} == {"interno", "externo"}
    # `por_modelo` agrupa por (modelo, ambiente): o mesmo modelo externo
    # usado por duas origens é UMA linha.
    modelos = {(b.modelo, b.ambiente): b for b in rel.por_modelo}
    assert set(modelos) == {("clip", "interno"), ("gemma-vision", "externo")}
    assert modelos[("gemma-vision", "externo")].chamadas == 2
    # `por_operacao` agrupa por (operacao, origem, ambiente): é o nível que
    # separa visão interna de externa, que a heurística antiga misturava.
    assert len(rel.por_operacao) == 3


def test_diario_agrupa_por_dia_local_ordenado_do_mais_recente():
    eventos = [
        EventoDiario(data="2026-10-06", origem="chat", tokens_entrada=10, tokens_saida=1, custo_usd=0.001),
        EventoDiario(data="2026-10-08", origem="chat", tokens_entrada=20, tokens_saida=2, custo_usd=0.002),
        EventoDiario(data="2026-10-08", origem="admin", tokens_entrada=None, tokens_saida=None, custo_usd=None),
    ]

    rel = montar_relatorio(
        period="7d",
        linhas=[],
        eventos_diarios=eventos,
        chats_encerrados_total=3,
        chats_encerrados_por_dia={"2026-10-08": 2, "2026-10-06": 1},
    )

    assert [d.data for d in rel.diario] == ["2026-10-08", "2026-10-06"]

    hoje = rel.diario[0]
    assert hoje.chats_encerrados == 2
    assert hoje.totais.chamadas == 2
    assert hoje.totais.custo_usd == 0.002
    assert hoje.totais.chamadas_sem_custo_medido == 1
    assert {b.origem for b in hoje.por_origem} == {"chat", "admin"}

    ontem = rel.diario[1]
    assert ontem.chats_encerrados == 1
    assert ontem.totais.chamadas == 1


def test_diario_inclui_dia_com_chat_encerrado_e_nenhum_uso_de_ia():
    rel = montar_relatorio(
        period="7d",
        linhas=[],
        eventos_diarios=[],
        chats_encerrados_total=1,
        chats_encerrados_por_dia={"2026-10-07": 1},
    )

    assert [d.data for d in rel.diario] == ["2026-10-07"]
    assert rel.diario[0].chats_encerrados == 1
    assert rel.diario[0].totais.chamadas == 0
    assert rel.diario[0].totais.custo_usd is None
