import asyncio

from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.db import models  # noqa: F401
from app.db.base import Base


async def main():
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("tables created")


asyncio.run(main())