"""Persistência de configurações de execução no PostgreSQL."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AppSetting


async def get_app_setting(session: AsyncSession, key: str, default: Any = None) -> Any:
    stmt = select(AppSetting.value).where(AppSetting.key == key)
    res = await session.execute(stmt)
    val = res.scalar_one_or_none()
    return val if val is not None else default


async def set_app_setting(session: AsyncSession, key: str, value: Any) -> None:
    stmt = select(AppSetting).where(AppSetting.key == key)
    res = await session.execute(stmt)
    setting = res.scalar_one_or_none()
    if setting is None:
        session.add(AppSetting(key=key, value=value))
    else:
        setting.value = value
    await session.commit()


async def save_multiple_app_settings(session: AsyncSession, settings_dict: dict[str, Any]) -> None:
    for key, value in settings_dict.items():
        stmt = select(AppSetting).where(AppSetting.key == key)
        res = await session.execute(stmt)
        setting = res.scalar_one_or_none()
        if setting is None:
            session.add(AppSetting(key=key, value=value))
        else:
            setting.value = value
    await session.commit()


async def get_all_app_settings(session: AsyncSession) -> dict[str, Any]:
    stmt = select(AppSetting.key, AppSetting.value)
    res = await session.execute(stmt)
    return dict(res.all())
