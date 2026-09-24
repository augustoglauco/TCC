"""Fire-and-forget helper para tasks disparadas por um endpoint HTTP sem
que a requisição espere por elas (ex.: download de modelo em
`app.api.local_models`, persistência de escalonamento em `app.api.chat`).

asyncio só guarda uma referência fraca a uma Task criada via
`create_task` — sem mais nada referenciando, ela pode ser coletada pelo
GC no meio da execução. Este módulo mantém a referência forte num set
module-level e a remove via `add_done_callback` assim que a tarefa
termina (sucesso ou erro), então o set só cresce enquanto há trabalho
genuinamente em andamento.

Achado no code-review (2026-09-24): `app.api.chat` e `app.api.local_models`
duplicavam esse exato padrão (set + create_task + add_done_callback) cada
um com sua própria variável `_background_tasks`.
"""

import asyncio
from collections.abc import Coroutine
from typing import Any

_background_tasks: set[asyncio.Task] = set()


def spawn_background_task(coro: Coroutine[Any, Any, None]) -> asyncio.Task:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task
