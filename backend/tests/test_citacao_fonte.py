import pytest

from app.router.citacao_fonte import FiltroCitacaoFonte, remover_citacoes_fonte


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("Tem display touchscreen [Fonte: idaccess.md].", "Tem display touchscreen."),
        (
            "Suporta 5.000 usuários (Fonte: torniquete-facial-datasheet.md).",
            "Suporta 5.000 usuários.",
        ),
        ("a [Fonte: x.md] b", "a b"),
        ("duas [Fonte: a.md] [Fonte: b.md] fontes", "duas fontes"),
        (
            "sem citação, só [colchetes] e (parênteses)",
            "sem citação, só [colchetes] e (parênteses)",
        ),
        ("[fonte: minúsculo.md] ok", " ok"),
        ("trecho [Fonte: sem fechar", "trecho [Fonte: sem fechar"),
    ],
)
def test_remove_citacoes_do_texto_completo(entrada, esperado):
    assert remover_citacoes_fonte(entrada) == esperado


@pytest.mark.parametrize("tamanho", [1, 2, 3, 5, 7])
def test_stream_picado_em_qualquer_ponto_da_citacao(tamanho):
    texto = (
        "Possui IP65 [Fonte: torniquete-facial-datasheet.md]. Aceita 5.000 usuários (Fonte: x.md)."
    )
    filtro = FiltroCitacaoFonte()
    saida = "".join(filtro.feed(texto[i : i + tamanho]) for i in range(0, len(texto), tamanho))
    saida += filtro.flush()

    assert saida == "Possui IP65. Aceita 5.000 usuários."
