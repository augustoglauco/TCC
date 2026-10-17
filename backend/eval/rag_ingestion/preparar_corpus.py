"""Prepara o corpus para ingestão, resolvendo os descartes silenciosos que a
Etapa 0 encontrou (Fase 10, R4 — `docs/EVALUATION.md` Seção 2.1).

Decisões do dono de 2026-10-17, depois de ver o relatório da Etapa 0:

1. **Converter as 4 imagens que o pipeline rejeita.** 3 `.tif` (formato fora
   de JPEG/PNG/WEBP, que `app.ocr.image_processor.detect_image_format` não
   reconhece) e 1 `.png` de 10,1 MB (formato válido, mas acima de
   `MAX_IMAGE_BYTES`). Viram JPEG com o lado maior limitado — o CLIP
   redimensiona para 224×224 de qualquer forma (`app.rag.clip_embedder`),
   então reduzir de 6966 px para 2000 px não perde nada em recuperação e
   resolve formato e tamanho de uma vez.
2. **Converter o `.html` para `.md`.** `REP iDClass/api_idclass_latest.html`
   tem ~55 mil chars de texto útil (a documentação da API do REP iDClass),
   mas `SUPPORTED_SUFFIXES = {".txt", ".md", ".pdf"}` em `app.rag.ingest`
   não inclui `.html` e `ingest_directory` pula o que não reconhece com um
   `continue` silencioso. Converter resolve sem mexer em código de produção.
3. **Os 11 PDFs degenerados ficam de fora** (nenhuma ação aqui). Dos 10
   diretórios afetados, 8 têm outro PDF legível e seguem cobertos; só
   `iDflexpro` e `iDClass Portaria 373` perdem a única fonte, e esses dois
   viram casos negativos do conjunto de perguntas sem resposta no corpus.

**Os originais não são apagados.** Os arquivos convertidos entram ao lado,
e o pipeline passa a enxergar a versão boa: o `.tif` continua rejeitado por
`detect_image_format` (inofensivo) e o `.html` continua fora de
`SUPPORTED_SUFFIXES`. Apagar 184 MB de `.tif` é irreversível e não traz
ganho nenhum para a avaliação — fica a critério do dono, fora deste script.

Idempotente: pula o que já foi convertido, comparando data de modificação.

Uso (a partir de `backend/`; não exige GPU, Qdrant, Postgres nem rede):

    .venv/bin/python eval/rag_ingestion/preparar_corpus.py
    .venv/bin/python eval/rag_ingestion/preparar_corpus.py --dry-run
"""

import argparse
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from app.ocr.image_processor import MAX_IMAGE_BYTES  # noqa: E402

RAIZ_REPO = Path(__file__).resolve().parents[3]
CORPUS = RAIZ_REPO / "docs" / "Manuais_fornecedor" / "ControlId"

# O lado maior do JPEG de saída. O CLIP reduz tudo a 224×224, então qualquer
# coisa acima disto é peso morto para a recuperação; 2000 px mantém a imagem
# utilizável para conferência humana sem chegar perto do teto de 10 MB.
LADO_MAXIMO = 2000
QUALIDADE_JPEG = 90

# As 4 imagens que a Etapa 0 apontou como rejeitadas pelo pipeline.
IMAGENS_A_CONVERTER = [
    "iDFace Max/iDFace-Max.tif",
    "IDBlock Facial/iDBlock-Facial-Preta.tif",
    "IDBlock Facial/iDBlock-Facial-Inox.tif",
    "IDBlock Facial/iDBlock-Next-Facial.png",
]

HTML_A_CONVERTER = "REP iDClass/api_idclass_latest.html"

# Fração mínima do texto limpo que o Markdown precisa recuperar para ser
# aceito. 0,80 porque a conversão perde legitimamente algum espaço em branco
# e texto de navegação; perder mais que 20% indica tag não mapeada em
# `_BLOCOS`, não ruído de formatação.
LIMIAR_RECUPERACAO_HTML = 0.80

# `.tif` de 78 MB estoura o limite anti-decompression-bomb do PIL. Aqui a
# fonte é o material do fornecedor, não entrada de usuário, então o limite
# não protege de nada e só impede a conversão.
Image.MAX_IMAGE_PIXELS = None


def _ja_atualizado(origem: Path, destino: Path) -> bool:
    return destino.exists() and destino.stat().st_mtime >= origem.stat().st_mtime


def converter_imagem(origem: Path, *, dry_run: bool) -> tuple[str, str]:
    """Converte para JPEG com o lado maior limitado. Devolve (status, detalhe)."""
    destino = origem.with_suffix(".jpg")
    if destino == origem:
        return "ignorado", "já é .jpg"
    if _ja_atualizado(origem, destino):
        return "ok", f"já convertido ({destino.stat().st_size / 1048576:.1f} MB)"
    if dry_run:
        return "faria", f"-> {destino.name}"

    with Image.open(origem) as im:
        largura, altura = im.size
        # RGBA/P/LA não existem em JPEG — achata sobre branco em vez de
        # descartar o canal alfa, que deixaria franja preta nas bordas.
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            fundo = Image.new("RGB", im.size, (255, 255, 255))
            fundo.paste(im, mask=im.split()[-1])
            im = fundo
        elif im.mode != "RGB":
            im = im.convert("RGB")
        if max(im.size) > LADO_MAXIMO:
            im.thumbnail((LADO_MAXIMO, LADO_MAXIMO), Image.LANCZOS)
        im.save(destino, "JPEG", quality=QUALIDADE_JPEG, optimize=True)

    tamanho = destino.stat().st_size
    if tamanho > MAX_IMAGE_BYTES:
        return "FALHOU", f"{tamanho / 1048576:.1f} MB ainda acima do teto de 10 MB"
    return "convertido", (
        f"{largura}x{altura} -> {im.size[0]}x{im.size[1]}, "
        f"{origem.stat().st_size / 1048576:.1f} MB -> {tamanho / 1048576:.1f} MB"
    )


# Tags que delimitam um bloco de texto. Inclui **tags customizadas**: o
# `api_idclass_latest.html` é um doc de API gerado por componentes (estilo
# Slate/Vue) e guarda o conteúdo em `<description>`, `<code>`, `<name>`,
# `<type>`, `<subtitle>`, `<alert>` — não em `<p>`/`<li>`. Uma primeira
# versão deste conversor olhava só tags HTML padrão e recuperava 4 mil dos
# 57 mil caracteres (93% de perda, silenciosa); daí a lista ser explícita e
# a conversão ser conferida por contagem de caracteres.
_BLOCOS = {
    "h1", "h2", "h3", "h4", "h5", "h6",
    "p", "li", "pre", "tr", "div", "td", "th", "blockquote", "dt", "dd",
    "title", "subtitle", "name", "type", "description", "content", "alert", "code",
}  # fmt: skip

_TITULOS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6, "title": 2, "subtitle": 3}


def html_para_markdown(html: str) -> str:
    """Converte HTML em Markdown simples, percorrendo os blocos-**folha** em
    ordem de documento.

    Folha = elemento de `_BLOCOS` que não contém outro elemento de
    `_BLOCOS`. Emitir só as folhas preserva a ordem do documento e evita
    contar o mesmo texto duas vezes (um `<div>` que embala dez
    `<description>` seria emitido junto com cada um deles).

    Não é um conversor de HTML geral — é o suficiente para o que o chunking
    do RAG consome: títulos, parágrafos, listas, tabelas e blocos de código.
    """
    sopa = BeautifulSoup(html, "html.parser")
    for tag in sopa(["script", "style", "nav", "noscript"]):
        tag.decompose()

    partes: list[str] = []
    for el in sopa.find_all(_BLOCOS):
        if el.find(_BLOCOS) is not None:
            continue  # não é folha: o conteúdo sai nos descendentes
        if el.name == "pre" or el.name == "code":
            bruto = el.get_text("\n", strip=True)
            if bruto:
                partes.append(f"\n```\n{bruto}\n```\n")
            continue
        texto = el.get_text(" ", strip=True)
        if not texto:
            continue
        if el.name in _TITULOS:
            partes.append(f"\n{'#' * _TITULOS[el.name]} {texto}\n")
        elif el.name == "li":
            partes.append(f"- {texto}")
        elif el.name in ("td", "th"):
            partes.append(f"| {texto} |")
        elif el.name == "alert":
            partes.append(f"> {texto}")
        else:
            partes.append(texto)

    md = "\n".join(partes)
    # Colapsa linhas vazias em excesso (vêm dos títulos e blocos de código,
    # que já abrem e fecham com \n) sem juntar blocos distintos.
    return re.sub(r"\n{3,}", "\n\n", md).strip() + "\n"


def converter_html(origem: Path, *, dry_run: bool) -> tuple[str, str]:
    destino = origem.with_suffix(".md")
    if _ja_atualizado(origem, destino):
        return "ok", f"já convertido ({len(destino.read_text(encoding='utf-8')):,} chars)"
    if dry_run:
        return "faria", f"-> {destino.name}"

    html = origem.read_text(encoding="utf-8", errors="replace")
    md = html_para_markdown(html)

    # Guarda contra perda silenciosa. A primeira versão deste conversor
    # recuperou 4 mil dos 57 mil caracteres porque o arquivo usa tags
    # customizadas, e nada no resultado indicava o problema — o .md era
    # gerado, o script dizia "convertido", e 93% do conteúdo tinha
    # desaparecido. Comparar com o texto limpo que o BeautifulSoup extrai
    # sem estrutura alguma é a checagem independente que faltava.
    sopa = BeautifulSoup(html, "html.parser")
    for tag in sopa(["script", "style", "nav", "noscript"]):
        tag.decompose()
    esperado = len(sopa.get_text(" ", strip=True))
    proporcao = len(md) / esperado if esperado else 1.0
    detalhe = (
        f"{len(html):,} chars de HTML -> {len(md):,} chars de Markdown "
        f"({proporcao:.0%} do texto limpo)"
    )
    if proporcao < LIMIAR_RECUPERACAO_HTML:
        return "FALHOU", f"{detalhe} — abaixo de {LIMIAR_RECUPERACAO_HTML:.0%}, .md não gravado"

    destino.write_text(md, encoding="utf-8")
    return "convertido", detalhe


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="só mostra o que faria")
    parser.add_argument("--corpus", type=Path, default=CORPUS)
    args = parser.parse_args(argv[1:])

    if not args.corpus.is_dir():
        print(f"ERRO: corpus não encontrado em {args.corpus}", file=sys.stderr)
        return 1

    falhas = 0
    print(f"Corpus: {args.corpus.relative_to(RAIZ_REPO)}\n")

    print("Imagens rejeitadas pelo pipeline -> JPEG:")
    for relativo in IMAGENS_A_CONVERTER:
        origem = args.corpus / relativo
        if not origem.exists():
            print(f"  [AUSENTE   ] {relativo}")
            falhas += 1
            continue
        status, detalhe = converter_imagem(origem, dry_run=args.dry_run)
        print(f"  [{status:10s}] {relativo}: {detalhe}")
        if status == "FALHOU":
            falhas += 1

    print("\nHTML -> Markdown:")
    origem = args.corpus / HTML_A_CONVERTER
    if not origem.exists():
        print(f"  [AUSENTE   ] {HTML_A_CONVERTER}")
        falhas += 1
    else:
        status, detalhe = converter_html(origem, dry_run=args.dry_run)
        print(f"  [{status:10s}] {HTML_A_CONVERTER}: {detalhe}")

    print(
        "\nOs 11 PDFs degenerados ficam de fora, por decisão de 2026-10-17 "
        "(nenhuma ação aqui).\nOriginais preservados: nada foi apagado."
    )
    if falhas:
        print(f"\n{falhas} problema(s). Veja acima.", file=sys.stderr)
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
