"""
app/core/config.py
Configuración central de LudusAcademia v2.
Clave nueva respecto a v1: SUPABASE_URL y SUPABASE_JWT_SECRET
para validar los tokens del panel docente sin mantener usuarios propios.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    # SQLite
    DATABASE_PATH: str = "./ludusacademia.db"

    # Supabase Auth
    SUPABASE_URL: str
    SUPABASE_JWT_SECRET: str

    # Comportamiento
    MAX_SYNC_PAYLOAD_KB: int = 50
    INVITE_CODE_EXPIRY_HOURS: int = 24
    ALLOW_PUBLIC_DOCENTE_ENDPOINTS: bool = False
    SEED_SAMPLE_DATA: bool = False
    SEED_DOCENTE_EMAIL: str = "maestro@test.com"
    SEED_DOCENTE_NOMBRE: str = "Docente Demo"
    SEED_GRUPO_NOMBRE: str = "Grupo Demo"
    SEED_ESCUELA_NOMBRE: str = "Escuela Demo LudusAcademia"
    SEED_ESTUDIANTE_UUID: str = "11111111-1111-1111-1111-111111111111"
    SEED_ESTUDIANTE_ALIAS: str = "Alumno Demo"
    SEED_CODIGO_VINCULACION: str = "LUDUDE"

    # CORS
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]

    @property
    def DATABASE_URL(self) -> str:
        return f"sqlite+aiosqlite:///{self.DATABASE_PATH}"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
