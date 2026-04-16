"""
Población inicial de la base de datos para despliegues de prueba.

Se ejecuta solo si SEED_SAMPLE_DATA=true y la BD todavía no tiene datos.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.models import CodigoVinculacion, Docente, Estudiante, EventoAprendizaje, Grupo
from app.db.session import AsyncSessionLocal

settings = get_settings()


async def seed_sample_data() -> None:
    if not settings.SEED_SAMPLE_DATA:
        return

    async with AsyncSessionLocal() as session:
        docentes_count = await session.scalar(select(func.count(Docente.id)))
        grupos_count = await session.scalar(select(func.count(Grupo.id)))

        if (docentes_count or 0) > 0 or (grupos_count or 0) > 0:
            return

        docente = Docente(
            supabase_uid="seed-demo-supabase-uid",
            correo=settings.SEED_DOCENTE_EMAIL,
            nombre_completo=settings.SEED_DOCENTE_NOMBRE,
        )
        session.add(docente)
        await session.flush()

        grupo = Grupo(
            id_docente=docente.id,
            nombre_grupo=settings.SEED_GRUPO_NOMBRE,
            nombre_escuela=settings.SEED_ESCUELA_NOMBRE,
        )
        session.add(grupo)
        await session.flush()

        estudiante = Estudiante(
            uuid_estudiante=settings.SEED_ESTUDIANTE_UUID,
            id_grupo=grupo.id,
            alias_estudiante=settings.SEED_ESTUDIANTE_ALIAS,
            monedas_totales=120,
        )
        session.add(estudiante)
        await session.flush()

        codigo = CodigoVinculacion(
            codigo=settings.SEED_CODIGO_VINCULACION,
            id_grupo=grupo.id,
            expira_el=datetime.now(timezone.utc) + timedelta(days=30),
            esta_usado=False,
        )
        evento = EventoAprendizaje(
            id_evento="seed-evento-1",
            uuid_estudiante=estudiante.uuid_estudiante,
            id_mision="mision-demo-1",
            errores=2,
            segundos_jugados=180,
            monedas_ganadas=40,
            fecha_dispositivo=datetime.now(timezone.utc),
        )

        session.add(codigo)
        session.add(evento)
        await session.commit()
