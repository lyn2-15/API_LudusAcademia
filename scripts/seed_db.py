"""Seeder manual para la base de datos de LudusAcademia.

Uso:
    python scripts/seed_db.py
"""
from __future__ import annotations

import asyncio

from app.db.seed import seed_default_data
from app.db.session import AsyncSessionLocal, init_db


async def main() -> None:
    await init_db()
    async with AsyncSessionLocal() as session:
        await seed_default_data(session)
        await session.commit()


if __name__ == "__main__":
    asyncio.run(main())