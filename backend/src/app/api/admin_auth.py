"""Dependência FastAPI compartilhada para restringir endpoints a
administradores autenticados.

Extraída de `app.api.admin_charts` (achado da revisão de 2026-10-04: a
checagem só existia lá — todo o resto de `/api/admin/*` e das telas
administrativas de RAG confiava só na UI do Next.js esconder a tela) para
não duplicar a mesma função em cada módulo de API administrativo.
"""

from typing import Annotated

from fastapi import Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import verificar_admin_por_token
from app.api.rag_dependencies import get_db_session


async def require_admin(
    session: AsyncSession = Depends(get_db_session),
    authorization: Annotated[str | None, Header()] = None,
    x_auth_token: Annotated[str | None, Header(alias="X-Auth-Token")] = None,
    token_param: Annotated[str | None, Query(alias="token")] = None,
) -> None:
    token: str | None = None
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
        elif len(parts) == 1:
            token = parts[0]
    elif x_auth_token:
        token = x_auth_token
    elif token_param:
        token = token_param

    if not token or not await verificar_admin_por_token(session, token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a administradores autenticados.",
        )
