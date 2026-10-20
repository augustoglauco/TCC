"""Etapa 0 da otimização de ingestão: auditoria do corpus que será ingerido
(Fase 10, R4 — ver `docs/EVALUATION.md` Seção 2.1).

Corpus: `docs/Manuais_fornecedor/ControlId/`, uma pasta por produto/linha.
Decisão do dono de 2026-10-17: **este** é o corpus da avaliação, e todo
gabarito (perguntas de documento, de imagem e de banco) tem de sair daqui —
os conjuntos anteriores, montados sobre outros documentos, não valem mais.

Precede todas as outras etapas porque um documento que o pipeline não
consegue ler é invisível ao RAG com QUALQUER combinação de modelo de
embedding, chunking ou índice. Medir parâmetros sobre um corpus que contém
esses arquivos contamina o resultado com um problema que não é de parâmetro,
é de extração — a mesma contaminação que tirou Q8/Q19 do conjunto em
2026-10-01, mas pior, porque aqui o arquivo *consta* como ingerido e rende
quase nada, sem erro em lugar nenhum.

A auditoria mede as três mídias contra as restrições **reais de produção**,
não contra bibliotecas genéricas:

- **PDFs** — via `app.rag.pdf_extract.extract_text_from_pdf` (o extrator de
  produção, com a detecção de 2 colunas), classificando por chars/página.
- **Imagens** — via `app.ocr.image_processor.detect_image_format` e
  `MAX_IMAGE_BYTES`, que é o que de fato barra um upload. Formato fora de
  JPEG/PNG/WEBP ou arquivo acima do teto é rejeitado pelo sistema, logo não
  pode ser gabarito de pergunta de imagem.
- **Pastas de produto** — cruzamento final: para cada pasta, se ela tem
  texto aproveitável, imagem válida, ambos ou nada. É isso que diz quais
  pastas podem sustentar pergunta de documento, de imagem, ou as duas.

# MVP: a auditoria só mede e classifica — não dispara OCR, não converte
# imagem, não reingere nada. As decisões que ela expõe (OCR x excluir do
# gabarito; converter .tif x descartar) são do dono, porque envolvem julgar
# se o conteúdo daquele arquivo é pertinente às perguntas.

Uso (a partir de `backend/`; não exige GPU, Qdrant, Postgres nem rede):

    .venv/bin/python eval/rag_ingestion/auditar_corpus.py
    .venv/bin/python eval/rag_ingestion/auditar_corpus.py <outra/pasta>

Salva `eval/rag_ingestion/auditoria_corpus.json`.
"""

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pdfplumber

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from app.ocr.image_processor import (  # noqa: E402
    MAX_IMAGE_BYTES,
    detect_image_format,
)
from app.rag.pdf_extract import extract_text_from_pdf  # noqa: E402

RAIZ_REPO = Path(__file__).resolve().parents[3]
CORPUS_PADRAO = RAIZ_REPO / "docs" / "Manuais_fornecedor" / "ControlId"
SAIDA = Path(__file__).parent / "auditoria_corpus.json"

# Limiar de chars/página abaixo do qual a camada de texto é considerada
# degenerada. 200 chars é ~1 parágrafo curto: menos que isso numa página
# inteira significa que o conteúdo real está em imagem, não em texto.
# Medido por página (não no total) para não penalizar datasheet de 1 página.
LIMIAR_CHARS_POR_PAGINA = 200

# Extensões que ao menos *parecem* imagem. O veredito não vem da extensão e
# sim de `detect_image_format` (magic bytes), igual à produção — a extensão
# só serve para decidir o que vale a pena abrir.
EXT_IMAGEM = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff"}


def _pasta_produto(caminho: Path, corpus: Path) -> str:
    """Primeiro nível sob o corpus — é o gabarito das perguntas de imagem."""
    relativo = caminho.relative_to(corpus)
    return relativo.parts[0] if len(relativo.parts) > 1 else "(raiz)"


def _classificar_pdf(chars: int, paginas: int) -> str:
    if chars == 0:
        return "sem_texto"
    if paginas and chars / paginas < LIMIAR_CHARS_POR_PAGINA:
        return "degenerado"
    return "util"


def auditar_pdfs(corpus: Path) -> list[dict]:
    itens = []
    for caminho in sorted(corpus.rglob("*.pdf")):
        item = {
            "arquivo": str(caminho.relative_to(corpus)),
            "pasta": _pasta_produto(caminho, corpus),
            "tamanho_kb": round(caminho.stat().st_size / 1024),
        }
        try:
            with pdfplumber.open(caminho) as pdf:
                paginas = len(pdf.pages)
            texto = extract_text_from_pdf(caminho)
        # `extract_text_from_pdf` só levanta `PdfExtractionError`, mas abrir
        # o PDF no pdfplumber levanta tipos variados (pdfminer) — um PDF
        # ilegível é um resultado válido da auditoria, não motivo para
        # derrubar a rodada inteira.
        except Exception as exc:
            itens.append({**item, "erro": f"{type(exc).__name__}: {exc}", "classificacao": "erro"})
            continue
        chars = len(texto)
        itens.append(
            {
                **item,
                "paginas": paginas,
                "chars": chars,
                "chars_por_pagina": round(chars / paginas) if paginas else 0,
                "classificacao": _classificar_pdf(chars, paginas),
            }
        )
    return itens


def auditar_imagens(corpus: Path) -> list[dict]:
    """Classifica cada imagem pelas duas restrições que a produção aplica:
    formato reconhecido por magic bytes e teto de `MAX_IMAGE_BYTES`."""
    itens = []
    candidatos = sorted(c for c in corpus.rglob("*") if c.suffix.lower() in EXT_IMAGEM)
    for caminho in candidatos:
        tamanho = caminho.stat().st_size
        # Só os primeiros bytes: `detect_image_format` lê magic bytes, e um
        # .tif de 60MB não precisa ir inteiro para a memória só para ser
        # reprovado.
        with caminho.open("rb") as fh:
            cabecalho = fh.read(16)
        formato = detect_image_format(cabecalho)
        excede = tamanho > MAX_IMAGE_BYTES
        if formato is None:
            classificacao = "formato_rejeitado"
        elif excede:
            classificacao = "acima_do_teto"
        else:
            classificacao = "valida"
        itens.append(
            {
                "arquivo": str(caminho.relative_to(corpus)),
                "pasta": _pasta_produto(caminho, corpus),
                "extensao": caminho.suffix.lower(),
                "tamanho_mb": round(tamanho / 1048576, 1),
                "formato_detectado": formato,
                "classificacao": classificacao,
            }
        )
    return itens


def auditar_outros(corpus: Path) -> list[dict]:
    """Arquivos que não são PDF nem imagem. `.url` é atalho de navegador
    (conteúdo está online, fora do corpus — exigiria o crawler); `.html` é
    conteúdo de texto ingerível de verdade e não deve ser esquecido."""
    itens = []
    for caminho in sorted(corpus.rglob("*")):
        if not caminho.is_file():
            continue
        ext = caminho.suffix.lower()
        if ext == ".pdf" or ext in EXT_IMAGEM:
            continue
        itens.append(
            {
                "arquivo": str(caminho.relative_to(corpus)),
                "pasta": _pasta_produto(caminho, corpus),
                "extensao": ext,
                "tamanho_kb": round(caminho.stat().st_size / 1024),
                "ingerivel": ext in {".html", ".htm", ".txt", ".md"},
            }
        )
    return itens


def cruzar_por_pasta(pdfs: list[dict], imagens: list[dict], corpus: Path) -> list[dict]:
    """Para cada pasta de produto: o que ela pode sustentar como gabarito."""
    pastas = sorted(p.name for p in corpus.iterdir() if p.is_dir())
    por_pasta: dict[str, dict] = defaultdict(
        lambda: {"pdfs_uteis": 0, "pdfs_degenerados": 0, "chars_uteis": 0, "imagens_validas": 0}
    )
    for item in pdfs:
        alvo = por_pasta[item["pasta"]]
        if item["classificacao"] == "util":
            alvo["pdfs_uteis"] += 1
            alvo["chars_uteis"] += item["chars"]
        elif item["classificacao"] in ("degenerado", "sem_texto"):
            alvo["pdfs_degenerados"] += 1
    for item in imagens:
        if item["classificacao"] == "valida":
            por_pasta[item["pasta"]]["imagens_validas"] += 1

    resultado = []
    for pasta in pastas:
        dados = por_pasta[pasta]
        tem_texto = dados["pdfs_uteis"] > 0
        tem_imagem = dados["imagens_validas"] > 0
        if tem_texto and tem_imagem:
            sustenta = "documento+imagem"
        elif tem_texto:
            sustenta = "so_documento"
        elif tem_imagem:
            sustenta = "so_imagem"
        else:
            sustenta = "nada"
        resultado.append({"pasta": pasta, **dados, "sustenta": sustenta})
    return resultado


def auditar(corpus: Path) -> dict:
    pdfs = auditar_pdfs(corpus)
    imagens = auditar_imagens(corpus)
    outros = auditar_outros(corpus)
    por_pasta = cruzar_por_pasta(pdfs, imagens, corpus)

    chars_uteis = sum(i["chars"] for i in pdfs if i["classificacao"] == "util")
    return {
        "corpus": str(corpus.relative_to(RAIZ_REPO)),
        "limiar_chars_por_pagina": LIMIAR_CHARS_POR_PAGINA,
        "max_image_bytes": MAX_IMAGE_BYTES,
        "pdfs": {
            "total": len(pdfs),
            "por_classificacao": dict(Counter(i["classificacao"] for i in pdfs)),
            "chars_total": sum(i.get("chars", 0) for i in pdfs),
            "chars_em_uteis": chars_uteis,
            # O que a Etapa 3 vai fatiar. A grade da Etapa 3 é em tokens;
            # 4,31 chars/token foi medido em pt-BR no tokenizer do modelo.
            "chunks_estimados": {
                f"{tok}_tokens": round(chars_uteis / (tok * 4.31))
                for tok in (128, 256, 512, 768, 1024)
            },
        },
        "imagens": {
            "total": len(imagens),
            "por_classificacao": dict(Counter(i["classificacao"] for i in imagens)),
            "por_extensao": dict(Counter(i["extensao"] for i in imagens)),
        },
        "outros": {
            "total": len(outros),
            "ingeriveis": sum(1 for i in outros if i["ingerivel"]),
            "por_extensao": dict(Counter(i["extensao"] for i in outros)),
        },
        "pastas": {
            "total": len(por_pasta),
            "por_capacidade": dict(Counter(p["sustenta"] for p in por_pasta)),
        },
        "itens_pdfs": pdfs,
        "itens_imagens": imagens,
        "itens_outros": outros,
        "itens_pastas": por_pasta,
    }


def _imprimir_pdfs(p: dict) -> None:
    print(f"PDFs ({p['total']}):")
    for classe in ("util", "degenerado", "sem_texto", "erro"):
        if classe in p["por_classificacao"]:
            print(f"  {classe:18s}: {p['por_classificacao'][classe]}")
    print(f"  chars extraíveis  : {p['chars_total']:,} ({p['chars_em_uteis']:,} nos úteis)")
    print(
        "  chunks estimados  : "
        + " · ".join(f"{k.split('_')[0]}t→~{v}" for k, v in p["chunks_estimados"].items())
    )


def _imprimir_imagens(i: dict) -> None:
    print(f"\nImagens ({i['total']}):")
    for classe, qtd in sorted(i["por_classificacao"].items()):
        print(f"  {classe:18s}: {qtd}")
    print(
        "  por extensão      : "
        + " · ".join(f"{k}={v}" for k, v in sorted(i["por_extensao"].items()))
    )


def _imprimir_outros_e_pastas(rel: dict) -> None:
    o = rel["outros"]
    print(f"\nOutros arquivos ({o['total']}, {o['ingeriveis']} ingerível(is)):")
    print("  " + " · ".join(f"{k}={v}" for k, v in sorted(o["por_extensao"].items())))

    print(
        f"\nPastas de produto ({rel['pastas']['total']}) — o que cada uma sustenta como gabarito:"
    )
    for capacidade, qtd in sorted(rel["pastas"]["por_capacidade"].items()):
        print(f"  {capacidade:18s}: {qtd}")


def _imprimir_problemas_pdf(itens_pdfs: list[dict]) -> None:
    problemas = [x for x in itens_pdfs if x["classificacao"] in ("degenerado", "sem_texto", "erro")]
    if not problemas:
        return
    print(f"\n{len(problemas)} PDFs exigem decisão (OCR ou sair do gabarito):")
    for x in sorted(problemas, key=lambda y: y.get("chars", -1)):
        print(f"  {x.get('chars', '?'):>6} chars /{x.get('paginas', '?'):>3} pág | {x['arquivo']}")


def _imprimir_imagens_rejeitadas(itens_imagens: list[dict]) -> None:
    ruins = [x for x in itens_imagens if x["classificacao"] != "valida"]
    if not ruins:
        return
    print(f"\n{len(ruins)} imagens o pipeline rejeita hoje:")
    for x in sorted(ruins, key=lambda y: -y["tamanho_mb"]):
        print(
            f"  [{x['classificacao']:18s}] {x['tamanho_mb']:6.1f} MB "
            f"fmt={x['formato_detectado']} | {x['arquivo']}"
        )


def _imprimir_pastas_fracas(itens_pastas: list[dict]) -> None:
    vazias = [x for x in itens_pastas if x["sustenta"] == "nada"]
    if vazias:
        print(f"\n{len(vazias)} pastas não sustentam gabarito nenhum:")
        for x in vazias:
            print(f"  {x['pasta']} (degenerados: {x['pdfs_degenerados']})")

    so_imagem = [x for x in itens_pastas if x["sustenta"] == "so_imagem"]
    if so_imagem:
        print(
            f"\n{len(so_imagem)} pastas só sustentam pergunta de IMAGEM (sem texto aproveitável):"
        )
        for x in so_imagem:
            print(
                f"  {x['pasta']} (imagens: {x['imagens_validas']}, "
                f"degenerados: {x['pdfs_degenerados']})"
            )


def _imprimir(rel: dict) -> None:
    print(f"Corpus: {rel['corpus']}\n")
    _imprimir_pdfs(rel["pdfs"])
    _imprimir_imagens(rel["imagens"])
    _imprimir_outros_e_pastas(rel)
    _imprimir_problemas_pdf(rel["itens_pdfs"])
    _imprimir_imagens_rejeitadas(rel["itens_imagens"])
    _imprimir_pastas_fracas(rel["itens_pastas"])


def main(argv: list[str]) -> int:
    corpus = Path(argv[1]).resolve() if len(argv) > 1 else CORPUS_PADRAO
    if not corpus.is_dir():
        print(f"ERRO: corpus não encontrado em {corpus}", file=sys.stderr)
        return 1

    relatorio = auditar(corpus)
    SAIDA.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")
    _imprimir(relatorio)
    print(f"\nRelatório completo: {SAIDA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
