"""Apaga do catálogo real os produtos que os testes de API deixaram para trás.

Até 2026-09-28, `test_admin_products_api.py`, `test_public_products_api.py`
e `test_catalog_extractor.py` rodavam contra o Postgres do desenvolvedor e
criavam produtos de verdade; quando um teste falhava no meio (ou, no caso do
"Produto Temporário", sempre), o produto ficava no catálogo e passava a
aparecer no chat (ex.: "Produto Teste Lote" entre os candidatos de vendas).
Os testes agora usam SQLite em memória (fixture `app_sqlite`).

Usa a API do admin (`DELETE /api/admin/produtos/{id}`), que também remove
as fotos e os vetores do CLIP no Qdrant. Só apaga nomes exatamente iguais aos
da lista abaixo e pede confirmação antes.

Uso (com o backend no ar):
    cd backend && uv run python scripts/limpar_produtos_de_teste.py
    cd backend && uv run python scripts/limpar_produtos_de_teste.py --sim   # sem perguntar
"""

import argparse
import sys

import httpx

# Nomes exatos criados pelos testes antigos.
NOMES_DE_TESTE = [
    "Produto Teste Lote",
    "Produto Com Foto Recortada",
    "Produto Temporário",
    "Câmera Bullet Z",
    "Câmera Bullet A",
    "Câmera Bullet 00 (Sem Estoque)",
    "Câmera Dome VIP 3200",
    "Switch 8 Portas",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--sim", action="store_true", help="apaga sem pedir confirmação")
    args = parser.parse_args()

    with httpx.Client(base_url=args.base_url, timeout=30) as cliente:
        encontrados = []
        for nome in NOMES_DE_TESTE:
            resposta = cliente.get("/api/admin/produtos", params={"termo": nome, "limit": 200})
            resposta.raise_for_status()
            encontrados += [p for p in resposta.json()["items"] if p["nome"] == nome]

        if not encontrados:
            print("Nenhum produto de teste no catálogo. Nada a fazer.")
            return 0

        print("Produtos de teste encontrados:")
        for produto in encontrados:
            print(f"  id={produto['id']:<6} {produto['nome']} ({produto['categoria']})")
        if not args.sim and input("Apagar estes produtos? [s/N] ").strip().lower() != "s":
            print("Nada foi apagado.")
            return 0

        for produto in encontrados:
            cliente.delete(f"/api/admin/produtos/{produto['id']}").raise_for_status()
            print(f"  apagado: id={produto['id']} {produto['nome']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
