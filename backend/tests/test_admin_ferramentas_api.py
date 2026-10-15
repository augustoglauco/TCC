"""Testes de `GET /api/admin/ferramentas` e do artefato do Graphify.

A sondagem dos servidores (Repowise/GitNexus) é substituída pelos testes —
nenhum teste sobe servidor nem depende de `localhost:3012`/`:4757` estarem
no ar, que é justamente o estado que a tela precisa distinguir.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import admin_ferramentas
from app.api.admin_ferramentas import router as ferramentas_router
from app.api.rag_dependencies import get_db_session
from app.config import get_settings


@pytest.fixture
def ferramentas_client(db_session):
    app = FastAPI()
    app.include_router(ferramentas_router)
    app.dependency_overrides[get_db_session] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def servidores_offline(monkeypatch):
    async def _offline(url: str):
        return False, f"Sem resposta em {url} (ConnectError)"

    monkeypatch.setattr(admin_ferramentas, "sondar_servidor", _offline)


@pytest.fixture
def servidores_online(monkeypatch):
    async def _online(url: str):
        return True, "HTTP 200"

    monkeypatch.setattr(admin_ferramentas, "sondar_servidor", _online)


@pytest.fixture
def graphify_em(tmp_path, monkeypatch):
    """Aponta `graphify_out_dir` para um diretório temporário e devolve o
    caminho do `graph.html` — criado ou não pelo próprio teste."""
    monkeypatch.setattr(get_settings(), "graphify_out_dir", str(tmp_path))
    return tmp_path / "graph.html"


@pytest.mark.asyncio
async def test_listar_ferramentas_requer_admin(ferramentas_client, servidores_offline):
    assert ferramentas_client.get("/api/admin/ferramentas").status_code == 403


@pytest.mark.asyncio
async def test_grafo_graphify_requer_admin(ferramentas_client, graphify_em):
    graphify_em.write_text("<html>grafo</html>", encoding="utf-8")
    resposta = ferramentas_client.get("/api/admin/ferramentas/graphify/grafo")
    assert resposta.status_code == 403


@pytest.mark.asyncio
async def test_lista_traz_as_tres_ferramentas(
    ferramentas_client, admin_headers, servidores_offline, graphify_em
):
    resposta = ferramentas_client.get("/api/admin/ferramentas", headers=admin_headers)

    assert resposta.status_code == 200
    ferramentas = resposta.json()["ferramentas"]
    assert [f["id"] for f in ferramentas] == ["graphify", "repowise", "gitnexus"]
    assert [f["tipo"] for f in ferramentas] == ["artefato", "servidor", "servidor"]
    # Toda ferramenta traz o comando de como gerar/subir o que falta — é o
    # que a tela mostra no lugar do iframe quando está offline.
    assert all(f["comando"] for f in ferramentas)


@pytest.mark.asyncio
async def test_servidores_offline_nao_derrubam_a_lista(
    ferramentas_client, admin_headers, servidores_offline, graphify_em
):
    """Repowise e GitNexus fora do ar é o caso normal (o desenvolvedor não
    deixa os dois servidores rodando o tempo todo), não um erro da tela."""
    resposta = ferramentas_client.get("/api/admin/ferramentas", headers=admin_headers)

    assert resposta.status_code == 200
    por_id = {f["id"]: f for f in resposta.json()["ferramentas"]}
    assert por_id["repowise"]["online"] is False
    assert por_id["gitnexus"]["online"] is False
    assert "Sem resposta" in por_id["repowise"]["detalhe"]


@pytest.mark.asyncio
async def test_servidores_online_expoem_url_para_embutir(
    ferramentas_client, admin_headers, servidores_online, graphify_em
):
    resposta = ferramentas_client.get("/api/admin/ferramentas", headers=admin_headers)

    por_id = {f["id"]: f for f in resposta.json()["ferramentas"]}
    assert por_id["repowise"]["online"] is True
    assert por_id["repowise"]["url"] == get_settings().repowise_web_url
    assert por_id["gitnexus"]["url"] == get_settings().gitnexus_web_url


@pytest.mark.asyncio
async def test_graphify_offline_quando_o_artefato_nao_existe(
    ferramentas_client, admin_headers, servidores_offline, graphify_em
):
    assert not graphify_em.exists()

    resposta = ferramentas_client.get("/api/admin/ferramentas", headers=admin_headers)

    graphify = resposta.json()["ferramentas"][0]
    assert graphify["online"] is False
    # Sem artefato não há URL para embutir — a tela cai no comando.
    assert graphify["url"] is None
    assert graphify["comando"] == "graphify update ."


@pytest.mark.asyncio
async def test_graphify_online_quando_o_artefato_existe(
    ferramentas_client, admin_headers, servidores_offline, graphify_em
):
    graphify_em.write_text("<html>grafo</html>", encoding="utf-8")

    resposta = ferramentas_client.get("/api/admin/ferramentas", headers=admin_headers)

    graphify = resposta.json()["ferramentas"][0]
    assert graphify["online"] is True
    assert graphify["url"] == "/api/admin/ferramentas/graphify/grafo"
    assert "MB" in graphify["detalhe"]


@pytest.mark.asyncio
async def test_grafo_graphify_devolve_o_html(ferramentas_client, admin_headers, graphify_em):
    graphify_em.write_text("<html><body>grafo do projeto</body></html>", encoding="utf-8")

    resposta = ferramentas_client.get(
        "/api/admin/ferramentas/graphify/grafo", headers=admin_headers
    )

    assert resposta.status_code == 200
    assert "grafo do projeto" in resposta.text
    assert resposta.headers["content-type"].startswith("text/html")


@pytest.mark.asyncio
async def test_grafo_graphify_404_com_instrucao_quando_falta(
    ferramentas_client, admin_headers, graphify_em
):
    resposta = ferramentas_client.get(
        "/api/admin/ferramentas/graphify/grafo", headers=admin_headers
    )

    assert resposta.status_code == 404
    assert "graphify update ." in resposta.json()["detail"]


@pytest.mark.asyncio
async def test_sondar_servidor_offline_devolve_falso_sem_levantar():
    """A sondagem real contra uma porta fechada não pode propagar exceção —
    a tela inteira dependeria de dois servidores locais estarem no ar."""
    online, detalhe = await admin_ferramentas.sondar_servidor("http://localhost:1")

    assert online is False
    assert "Sem resposta" in detalhe


class _ProcessoFalso:
    def __init__(self, codigo: int, saida: bytes):
        self.returncode = codigo
        self._saida = saida

    async def communicate(self):
        return self._saida, b""


@pytest.mark.asyncio
async def test_atualizar_graphify_requer_admin(ferramentas_client):
    assert ferramentas_client.post("/api/admin/ferramentas/graphify/atualizar").status_code == 403


@pytest.mark.asyncio
async def test_atualizar_graphify_roda_update_e_devolve_saida(
    ferramentas_client, admin_headers, graphify_em, monkeypatch
):
    chamadas = []

    async def _falso(*args, **kwargs):
        chamadas.append((args, kwargs))
        return _ProcessoFalso(0, b"grafo atualizado\n")

    monkeypatch.setattr(admin_ferramentas.shutil, "which", lambda _n: "/usr/bin/graphify")
    monkeypatch.setattr(admin_ferramentas.asyncio, "create_subprocess_exec", _falso)

    resposta = ferramentas_client.post(
        "/api/admin/ferramentas/graphify/atualizar", headers=admin_headers
    )

    assert resposta.status_code == 200
    assert resposta.json() == {"sucesso": True, "saida": "grafo atualizado"}
    assert chamadas[0][0][1:] == ("update", ".")
    assert chamadas[0][1]["cwd"] == graphify_em.parent.parent


@pytest.mark.asyncio
async def test_atualizar_graphify_falha_do_comando_nao_e_erro_http(
    ferramentas_client, admin_headers, graphify_em, monkeypatch
):
    async def _falso(*args, **kwargs):
        return _ProcessoFalso(1, b"boom")

    monkeypatch.setattr(admin_ferramentas.shutil, "which", lambda _n: "/usr/bin/graphify")
    monkeypatch.setattr(admin_ferramentas.asyncio, "create_subprocess_exec", _falso)

    resposta = ferramentas_client.post(
        "/api/admin/ferramentas/graphify/atualizar", headers=admin_headers
    )

    assert resposta.status_code == 200
    assert resposta.json() == {"sucesso": False, "saida": "boom"}


@pytest.mark.asyncio
async def test_atualizar_graphify_503_sem_cli(
    ferramentas_client, admin_headers, graphify_em, monkeypatch
):
    monkeypatch.setattr(admin_ferramentas.shutil, "which", lambda _n: None)

    resposta = ferramentas_client.post(
        "/api/admin/ferramentas/graphify/atualizar", headers=admin_headers
    )

    assert resposta.status_code == 503


@pytest.mark.asyncio
async def test_atualizar_gitnexus_roda_analyze_index_only(
    ferramentas_client, admin_headers, graphify_em, monkeypatch
):
    chamadas = []

    async def _falso(*args, **kwargs):
        chamadas.append(args)
        return _ProcessoFalso(0, b"indexado")

    monkeypatch.setattr(admin_ferramentas.shutil, "which", lambda n: f"/usr/bin/{n}")
    monkeypatch.setattr(admin_ferramentas.asyncio, "create_subprocess_exec", _falso)

    resposta = ferramentas_client.post(
        "/api/admin/ferramentas/gitnexus/atualizar", headers=admin_headers
    )

    assert resposta.status_code == 200
    assert resposta.json() == {"sucesso": True, "saida": "indexado"}
    assert chamadas[0][-2:] == ("analyze", "--index-only")


@pytest.mark.asyncio
async def test_atualizar_ferramenta_desconhecida_404(ferramentas_client, admin_headers):
    resposta = ferramentas_client.post(
        "/api/admin/ferramentas/repowise/atualizar", headers=admin_headers
    )
    assert resposta.status_code == 404
