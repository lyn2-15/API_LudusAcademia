"""
app/db/session.py
Motor SQLite asíncrono con aiosqlite.

Nota importante sobre SQLite + FastAPI async:
  SQLite serializa los writes (un writer a la vez). Para una API escolar
  con carga moderada (~30-50 alumnos sincronizando) esto es perfectamente
  viable. Si la demanda escala, se puede migrar a PostgreSQL cambiando
  solo la DATABASE_URL y quitando check_same_thread.

WAL mode (Write-Ahead Logging) se activa en la inicialización para
permitir lecturas concurrentes mientras hay un write en curso.
"""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import event, text

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.APP_ENV == "development",
    connect_args={"check_same_thread": False},
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def init_db():
    """
    Crea todas las tablas y activa WAL mode.
    Se llama una vez al arrancar la app (lifespan).
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # WAL mode: lecturas no bloquean escrituras
        await conn.execute(text("PRAGMA journal_mode=WAL"))
        await conn.execute(text("PRAGMA foreign_keys=ON"))


async def get_db() -> AsyncSession:
    """Dependencia FastAPI: inyecta una sesión de BD por request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
