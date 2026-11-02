"""Remove citações de fonte do texto que o LLM devolve ao cliente.

O RAG rotula cada trecho com `[Fonte: arquivo]` para o modelo separar
produtos parecidos, mas a fonte é informação do painel de métricas
(`rag_chunks`), não do texto da resposta. Mesmo instruído a não citar, o
modelo local às vezes copia o rótulo (`[Fonte: x.md]` ou `(Fonte: x.md)`),
então o stream passa por este filtro (2026-11-02).

# MVP: só os formatos `[Fonte: ...]` e `(Fonte: ...)`; citação em outro
# formato passa.
"""

_FECHAMENTO = {"[": "]", "(": ")"}
_ROTULO = "fonte"
_BUFFER_MAX = 300  # trecho aberto que nunca fecha é liberado como texto normal


class FiltroCitacaoFonte:
    """Filtro incremental: `feed()` por pedaço do stream, `flush()` no fim."""

    def __init__(self) -> None:
        self._buf = ""
        self._espacos = ""  # espaços já vistos, soltos só se não precederem uma citação

    def feed(self, texto: str) -> str:
        self._buf += texto
        saida: list[str] = []
        while self._buf:
            i = next((k for k, c in enumerate(self._buf) if c in _FECHAMENTO), -1)
            if i < 0:
                saida.append(self._soltar(self._buf))
                self._buf = ""
                break
            if i:
                saida.append(self._soltar(self._buf[:i]))
                self._buf = self._buf[i:]
            if not self._tratar_abertura(saida):
                break
        return "".join(saida)

    def flush(self) -> str:
        saida = self._soltar(self._buf) + self._espacos
        self._buf = ""
        self._espacos = ""
        return saida

    def _tratar_abertura(self, saida: list[str]) -> bool:
        """Processa o buffer que começa em `[`/`(`. False = precisa de mais texto."""
        abertura = self._buf[0]
        inicio = self._buf[1 : 1 + len(_ROTULO)].lower()
        if not _ROTULO.startswith(inicio) and inicio != _ROTULO:
            saida.append(self._soltar(abertura))
            self._buf = self._buf[1:]
            return True
        if len(inicio) < len(_ROTULO):
            return False  # ainda pode virar "Fonte"
        fim = self._buf.find(_FECHAMENTO[abertura])
        if fim >= 0:
            self._buf = self._buf[fim + 1 :]
            self._espacos = ""  # o espaço antes da citação some junto
            return True
        if len(self._buf) > _BUFFER_MAX:
            saida.append(self._soltar(abertura))
            self._buf = self._buf[1:]
            return True
        return False

    def _soltar(self, texto: str) -> str:
        """Emite `texto` segurando os espaços finais até saber o que vem depois."""
        corpo = texto.rstrip(" ")
        pendente = texto[len(corpo) :]
        if not corpo:
            self._espacos += pendente
            return ""
        saida = self._espacos + corpo
        self._espacos = pendente
        return saida


def remover_citacoes_fonte(texto: str) -> str:
    """Versão de uma passada só, para texto completo."""
    filtro = FiltroCitacaoFonte()
    return filtro.feed(texto) + filtro.flush()
