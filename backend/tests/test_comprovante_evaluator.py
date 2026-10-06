"""Testes unitários do serviço ComprovanteEvaluator (análise e auditoria financeira por LLM/OCR)."""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock

from app.services.comprovante_evaluator import ComprovanteEvaluator, ParecerComprovante


@pytest.mark.asyncio
async def test_avaliar_comprovante_txt_valido():
    conteudo_txt = """
    COMPROVANTE DE PAGAMENTO PIX
    Valor: R$ 1.500,00
    Data: 05/10/2026
    ID Transação: E1234567890
    Favorecido: Minha Empresa B2B LTDA
    """
    evaluator = ComprovanteEvaluator()
    parecer = await evaluator.avaliar_texto(conteudo_txt, valor_devido=Decimal("1500.00"))

    assert parecer.valido is True
    assert parecer.valor_pago == Decimal("1500.00")
    assert parecer.divergencia == Decimal("0.00")
    assert parecer.codigo_transacao == "E1234567890"


@pytest.mark.asyncio
async def test_avaliar_comprovante_txt_divergente():
    conteudo_txt = """
    COMPROVANTE DE PAGAMENTO PIX
    Valor: R$ 1.200,00
    ID Transação: E99887766
    """
    evaluator = ComprovanteEvaluator()
    parecer = await evaluator.avaliar_texto(conteudo_txt, valor_devido=Decimal("1500.00"))

    assert parecer.valido is False
    assert parecer.valor_pago == Decimal("1200.00")
    assert parecer.divergencia == Decimal("-300.00")
    assert "divergência" in parecer.justificativa.lower() or "divergente" in parecer.justificativa.lower()


@pytest.mark.asyncio
async def test_avaliar_texto_invalido():
    conteudo_txt = "Bom dia, gostaria de saber se vocês entregam em Curitiba?"
    evaluator = ComprovanteEvaluator()
    parecer = await evaluator.avaliar_texto(conteudo_txt, valor_devido=Decimal("500.00"))

    assert parecer.valido is False
    assert parecer.valor_pago == Decimal("0.00")


@pytest.mark.asyncio
async def test_avaliar_com_llm_client_mock():
    mock_llm = AsyncMock()
    mock_llm.generate.return_value = AsyncMock(
        text='{"comprovante_valido": true, "valor_pago": 2500.50, "codigo_transacao": "PIX-XYZ-999", "justificativa": "Comprovante validado com sucesso"}'
    )

    evaluator = ComprovanteEvaluator(llm_client=mock_llm)
    parecer = await evaluator.avaliar_texto(
        "texto do comprovante",
        valor_devido=Decimal("2500.50"),
    )

    assert parecer.valido is True
    assert parecer.valor_pago == Decimal("2500.50")
    assert parecer.divergencia == Decimal("0.00")
    assert parecer.codigo_transacao == "PIX-XYZ-999"


@pytest.mark.asyncio
async def test_avaliar_texto_retorna_tokens_usados_pelo_llm():
    """Achado de 2026-10-05 (usuário reportou que os tokens do modelo
    interno não apareciam em Métricas): `avaliar_texto` descartava
    `prompt_tokens`/`completion_tokens` da resposta do LLM, então essas
    chamadas nunca contavam em 'Tokens Internos (GPU Local)'."""
    mock_llm = AsyncMock()
    mock_response = AsyncMock(
        text='{"comprovante_valido": true, "valor_pago": 500.00, "justificativa": "ok"}',
    )
    mock_response.prompt_tokens = 230
    mock_response.completion_tokens = 60
    mock_llm.generate.return_value = mock_response

    evaluator = ComprovanteEvaluator(llm_client=mock_llm)
    parecer = await evaluator.avaliar_texto("texto do comprovante", valor_devido=Decimal("500.00"))

    assert parecer.prompt_tokens == 230
    assert parecer.completion_tokens == 60


@pytest.mark.asyncio
async def test_avaliar_texto_sem_llm_nao_tem_tokens():
    # Fallback heurístico (sem llm_client) não faz chamada nenhuma a LLM.
    evaluator = ComprovanteEvaluator()
    parecer = await evaluator.avaliar_texto(
        "COMPROVANTE DE PAGAMENTO PIX\nValor: R$ 500,00", valor_devido=Decimal("500.00")
    )
    assert parecer.prompt_tokens is None
    assert parecer.completion_tokens is None


@pytest.mark.asyncio
async def test_extrair_texto_documento_txt():
    evaluator = ComprovanteEvaluator()
    texto = evaluator.extrair_texto(b"Comprovante em arquivo texto", "comprovante.txt")
    assert texto == "Comprovante em arquivo texto"
