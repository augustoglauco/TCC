"""Monta `imagens/dataset.json`, o conjunto de imagem do benchmark (R2/R5).

Junta, de forma determinística e idempotente:
  - 23 positivas: as fotos reservadas como consulta do CLIP (`holdout.json`);
  - 48 negativas de `negativos/manifest.json` (30 de catálogo genérico + 18 de
    controle de acesso de outras marcas, que são as que testam a discriminação
    que importa);
  - 1 negativa de comprovante bancário, o caso do fluxo real de pagamento.

`aceitos` (termos que contam como acerto de categoria) só existe para as 7
positivas escritas à mão em 2026-10-17; nas demais fica vazio e o benchmark
cobra apenas `e_do_portfolio`. Inventar categoria para as outras 16 criaria
gabarito sem revisão.

Uso:
    .venv/bin/python eval/model_benchmark/montar_dataset_imagem.py
"""

import json
from pathlib import Path

BASE_DIR = Path(__file__).parent
IMAGENS = BASE_DIR / "imagens"
ARQ_ORIGEM = "docs/Manuais_fornecedor/ControlId"

ACEITOS = {
    "iDFace Max": ["facial", "reconhecimento", "biometri", "controle de acesso", "idface"],
    "iDAccess Pro": ["controle de acesso", "biometri", "leitor", "teclado", "idaccess"],
    "REP iDClass": ["ponto", "rep", "registrador", "relógio", "relogio", "idclass"],
    "iDBox": ["controlador", "controle de acesso", "módulo", "modulo", "central", "idbox"],
    "iDAccess Nano": ["controle de acesso", "leitor", "biometri", "idaccess", "nano"],
    "IDPower": ["fonte", "alimentação", "alimentacao", "nobreak", "energia", "idpower"],
    "Print iD Touch": ["impressora", "print", "etiqueta", "crachá", "cracha", "terminal"],
}

COMPROVANTE = {
    "id": "neg_comprovante",
    "caminho": "backend/eval/model_benchmark/imagens/negativo-comprovante-bancario.jpg",
    "produto_esperado": "(nenhum — comprovante de depósito bancário)",
    "e_do_portfolio": False,
    "aceitos": [],
    "origem": "comprovante",
}


def montar() -> dict:
    holdout = json.loads((IMAGENS / "holdout.json").read_text(encoding="utf-8"))["consultas"]
    manifest = json.loads((IMAGENS / "negativos" / "manifest.json").read_text(encoding="utf-8"))

    casos = []
    for i, c in enumerate(holdout, start=1):
        casos.append(
            {
                "id": f"pos_{i:02d}",
                "caminho": f"{ARQ_ORIGEM}/{c['arquivo']}",
                "produto_esperado": c["produto_esperado"],
                "e_do_portfolio": True,
                "aceitos": ACEITOS.get(c["produto_esperado"], []),
                "origem": "holdout",
            }
        )
    for i, n in enumerate(manifest, start=1):
        casos.append(
            {
                "id": f"neg_{i:02d}",
                "caminho": n["caminho_relativo"],
                "produto_esperado": f"(nenhum — {n['titulo']})",
                "e_do_portfolio": False,
                "aceitos": [],
                "origem": n["categoria"],
            }
        )
    casos.append(COMPROVANTE)
    return {
        "_nota": (
            "Conjunto de imagem do benchmark (R2/R5), montado por "
            "montar_dataset_imagem.py. Gabarito exato por construção (pasta do "
            "fornecedor / manifesto de negativas): não passa por revisão humana."
        ),
        "_limitacao": (
            "23 positivas -> IC 95% de ~±16 pp a p=0,80 (decisão do dono, "
            "2026-10-18). As 5 pastas com uma foto só ficam fora. Categoria só é "
            "cobrada nas positivas com `aceitos` (7); nas outras, só e_do_portfolio. "
            "As negativas genéricas são miniaturas de ~9 KB e as positivas fotos de "
            "~0,4 MB: a diferença de resolução pode inflar a separação."
        ),
        "casos": casos,
    }


if __name__ == "__main__":
    dados = montar()
    (IMAGENS / "dataset.json").write_text(
        json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    pos = sum(1 for c in dados["casos"] if c["e_do_portfolio"])
    print(f"{len(dados['casos'])} casos: {pos} positivos, {len(dados['casos']) - pos} negativos")
