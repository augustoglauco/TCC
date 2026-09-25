"""Autenticação do MCP B2B por chave estática por parceiro (R12, Fase 5) — ver
decisão de 2026-09-25 em `docs/ARCHITECTURE.md` §6.

Cada fornecedor habilitado recebe uma chave secreta e a envia em toda
requisição como `Authorization: Bearer <chave>` (cabeçalho padrão de
autenticação do MCP). A verificação usa o suporte nativo do SDK: o
`TokenVerifier` abaixo é plugado no `MCPServer` em modo *resource server*,
então chave ausente ou errada recebe `401` antes de chegar a qualquer
recurso ou ferramenta.

# MVP: autenticação por chave estática por parceiro (Bearer), sem OAuth,
# escopos, expiração nem rate limiting — revogar é tirar a entrada do `.env`
# e reiniciar o servidor.
"""

import hmac
from urllib.parse import urlsplit

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.transport_security import TransportSecuritySettings


class ChavesParceirosInvalidasError(ValueError):
    """`MCP_B2B_PARTNER_KEYS` mal formatado — o servidor não deve subir."""


# Chave curta demais é fácil de adivinhar; 16 caracteres já barra "123" ou
# "teste" sem atrapalhar quem gera a chave com `secrets.token_urlsafe(32)`.
_TAMANHO_MINIMO_CHAVE = 16


def carregar_chaves_parceiros(valor: str) -> dict[str, str]:
    """Lê `MCP_B2B_PARTNER_KEYS` (`nome:chave,nome2:chave2`) e devolve
    `{chave: nome}`. Vazio devolve `{}` (quem chama decide recusar a
    subida). Formato inválido, nome ou chave repetidos, ou chave curta
    levantam `ChavesParceirosInvalidasError` — melhor o servidor não subir
    do que subir aceitando menos (ou mais) do que o configurado."""
    chaves: dict[str, str] = {}
    nomes: set[str] = set()
    for entrada in (parte.strip() for parte in valor.split(",")):
        if not entrada:
            continue
        nome, separador, chave = entrada.partition(":")
        nome, chave = nome.strip(), chave.strip()
        if not separador or not nome or not chave:
            raise ChavesParceirosInvalidasError(
                "Entrada inválida em MCP_B2B_PARTNER_KEYS (esperado nome:chave): "
                f"{nome or entrada!r}"
            )
        if len(chave) < _TAMANHO_MINIMO_CHAVE:
            raise ChavesParceirosInvalidasError(
                f"Chave do parceiro {nome!r} tem menos de {_TAMANHO_MINIMO_CHAVE} caracteres."
            )
        if nome in nomes:
            raise ChavesParceirosInvalidasError(
                f"Parceiro {nome!r} repetido em MCP_B2B_PARTNER_KEYS."
            )
        if chave in chaves:
            raise ChavesParceirosInvalidasError(
                f"Parceiros {chaves[chave]!r} e {nome!r} usam a mesma chave."
            )
        nomes.add(nome)
        chaves[chave] = nome
    return chaves


class ChaveParceiroVerifier:
    """`TokenVerifier` do SDK: a "token" é a chave do parceiro. Devolve um
    `AccessToken` com `client_id` = nome do parceiro (lido depois por
    `parceiro_atual()` para o log de cada ferramenta), ou `None` para chave
    desconhecida — o SDK responde `401`."""

    def __init__(self, chaves: dict[str, str]) -> None:
        self._chaves = dict(chaves)

    async def verify_token(self, token: str) -> AccessToken | None:
        # Compara com todas as chaves em tempo constante (`compare_digest`),
        # sem sair no primeiro acerto — não dá pista, pelo tempo de
        # resposta, de quanto da chave estava certo.
        parceiro = None
        for chave, nome in self._chaves.items():
            if hmac.compare_digest(token.encode(), chave.encode()):
                parceiro = nome
        if parceiro is None:
            return None
        return AccessToken(token=token, client_id=parceiro, scopes=[])


def configuracao_auth(url_publica: str) -> AuthSettings:
    """`AuthSettings` do SDK em modo *resource server*. Não há servidor OAuth
    (MVP): `issuer_url` e `resource_server_url` apontam para o próprio
    endereço público só porque o SDK publica esses metadados (RFC 9728);
    quem autentica é o `ChaveParceiroVerifier`. `validate_token_resource`
    fica `False` porque a chave estática não carrega audiência."""
    return AuthSettings(
        issuer_url=_origem(url_publica),
        resource_server_url=url_publica,
        validate_token_resource=False,
    )


def seguranca_de_transporte(url_publica: str | None) -> TransportSecuritySettings:
    """Mantém a proteção do SDK contra DNS rebinding (só aceita `Host`
    conhecidos), acrescentando o host público: atrás do Caddy o servidor
    escuta em `127.0.0.1`, mas as requisições chegam com
    `Host: <domínio DuckDNS>:8443`, que o padrão do SDK recusaria."""
    hosts = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
    origens = ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"]
    if url_publica:
        partes = urlsplit(url_publica)
        hosts.append(partes.netloc)
        origens.append(_origem(url_publica))
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True, allowed_hosts=hosts, allowed_origins=origens
    )


class AutenticacaoMcpB2B:
    """O que `scripts/run_mcp_b2b_server.py` precisa para subir o servidor
    com autenticação: verificador de chave, `AuthSettings` e hosts aceitos."""

    def __init__(
        self,
        verificador: ChaveParceiroVerifier,
        auth: AuthSettings,
        seguranca: TransportSecuritySettings,
        parceiros: list[str],
    ) -> None:
        self.verificador = verificador
        self.auth = auth
        self.seguranca = seguranca
        self.parceiros = parceiros


def preparar_autenticacao(
    partner_keys: str, url_publica: str, host: str, port: int
) -> AutenticacaoMcpB2B:
    """Monta a autenticação a partir de `MCP_B2B_PARTNER_KEYS` e
    `MCP_B2B_PUBLIC_URL`. **Falha fechada:** sem nenhuma chave levanta
    `ChavesParceirosInvalidasError` e o servidor não sobe — em qualquer
    host, porque mesmo em `127.0.0.1` ele fica público através do Caddy.
    Sem `url_publica` (uso só local), usa `http://host:port/mcp`."""
    chaves = carregar_chaves_parceiros(partner_keys)
    if not chaves:
        raise ChavesParceirosInvalidasError(
            "MCP_B2B_PARTNER_KEYS vazio: o MCP B2B não sobe sem pelo menos uma "
            "chave de parceiro (ver docs/ARCHITECTURE.md §6)."
        )
    url = url_publica.strip() or f"http://{host}:{port}/mcp"
    return AutenticacaoMcpB2B(
        verificador=ChaveParceiroVerifier(chaves),
        auth=configuracao_auth(url),
        seguranca=seguranca_de_transporte(url_publica.strip() or None),
        parceiros=sorted(chaves.values()),
    )


def parceiro_atual() -> str:
    """Nome do parceiro autenticado na requisição em andamento, ou
    `"sem-autenticacao"` quando o servidor é chamado sem HTTP (testes que
    usam `server.call_tool(...)` direto)."""
    token = get_access_token()
    return token.client_id if token is not None else "sem-autenticacao"


def _origem(url: str) -> str:
    partes = urlsplit(url)
    return f"{partes.scheme}://{partes.netloc}"
