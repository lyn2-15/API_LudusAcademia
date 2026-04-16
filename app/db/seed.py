"""
Poblado idempotente de datos iniciales para despliegues de producción.

Objetivo:
  - Crear un docente Supabase conocido
  - Asegurar que exista el grupo 1 asignado a ese docente
  - Insertar datos mínimos de analítica para probar el dashboard

El seed es seguro para múltiples ejecuciones: solo crea lo que falta.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import CodigoVinculacion, Docente, Estudiante, EventoAprendizaje, Grupo

settings = get_settings()

SEED_GRUPO_ID = 1
SEED_GRUPO_NOMBRE = "Grupo 1"
SEED_ESTUDIANTE_UUID = "11111111-1111-4111-8111-111111111111"


async def seed_default_data(session: AsyncSession) -> None:
    """Crea datos base si la semilla está habilitada."""
    if not (settings.SUPABASE_SEED_ENABLED or settings.APP_ENV.lower() == "production"):
        return

    if not settings.SUPABASE_SEED_UID:
        return

    docente = await _get_or_create_docente(session)
    grupo = await _get_or_create_grupo(session, docente)
    estudiante = await _get_or_create_estudiante(session, grupo)
    await _seed_eventos(session, estudiante)
    await _seed_codigo_vinculacion(session, grupo.id)


async def _get_or_create_docente(session: AsyncSession) -> Docente:
    result = await session.execute(
        select(Docente).where(Docente.supabase_uid == settings.SUPABASE_SEED_UID)
    )
    docente = result.scalar_one_or_none()

    if docente:
        if not docente.correo:
            docente.correo = settings.SUPABASE_SEED_EMAIL
        if not docente.nombre_completo:
            docente.nombre_completo = "Maestro Demo"
        return docente

    docente = Docente(
        supabase_uid=settings.SUPABASE_SEED_UID,
        correo=settings.SUPABASE_SEED_EMAIL,
        nombre_completo="Maestro Demo",
    )
    session.add(docente)
    await session.flush()
    return docente


async def _get_or_create_grupo(session: AsyncSession, docente: Docente) -> Grupo:
    grupo = await session.get(Grupo, SEED_GRUPO_ID)
    if grupo:
        if grupo.id_docente != docente.id:
            grupo.id_docente = docente.id
        if not grupo.nombre_grupo:
            grupo.nombre_grupo = SEED_GRUPO_NOMBRE
        return grupo

    grupo = Grupo(
        id=SEED_GRUPO_ID,
        id_docente=docente.id,
        nombre_grupo=SEED_GRUPO_NOMBRE,
    )
    session.add(grupo)
    await session.flush()
    return grupo


async def _get_or_create_estudiante(session: AsyncSession, grupo: Grupo) -> Estudiante:
    estudiante = await session.get(Estudiante, SEED_ESTUDIANTE_UUID)
    if estudiante:
        estudiante.id_grupo = grupo.id
        if not estudiante.alias_estudiante:
            estudiante.alias_estudiante = "Alumno 1"
        return estudiante

    estudiante = Estudiante(
        uuid_estudiante=SEED_ESTUDIANTE_UUID,
        id_grupo=grupo.id,
        alias_estudiante="Alumno 1",
        monedas_totales=120,
    )
    session.add(estudiante)
    await session.flush()
    return estudiante


async def _seed_eventos(session: AsyncSession, estudiante: Estudiante) -> None:
    count_result = await session.execute(
        select(func.count(EventoAprendizaje.id_evento)).where(
            EventoAprendizaje.uuid_estudiante == estudiante.uuid_estudiante
        )
    )
    total_eventos = count_result.scalar_one()
    if total_eventos:
        return

    now = datetime.now(timezone.utc)
    eventos = [
        EventoAprendizaje(
            id_evento="22222222-2222-4222-8222-222222222221",
            uuid_estudiante=estudiante.uuid_estudiante,
            id_mision="mision_alfabetizacion_01",
            errores=2,
            segundos_jugados=420,
            monedas_ganadas=40,
            fecha_dispositivo=now - timedelta(days=2),
            fecha_servidor=now - timedelta(days=2),
        ),
        EventoAprendizaje(
            id_evento="22222222-2222-4222-8222-222222222222",
            uuid_estudiante=estudiante.uuid_estudiante,
            id_mision="mision_alfabetizacion_02",
            errores=1,
            segundos_jugados=360,
            monedas_ganadas=35,
            fecha_dispositivo=now - timedelta(days=1),
            fecha_servidor=now - timedelta(days=1),
        ),
        EventoAprendizaje(
            id_evento="22222222-2222-4222-8222-222222222223",
            uuid_estudiante=estudiante.uuid_estudiante,
            id_mision="mision_alfabetizacion_03",
            errores=0,
            segundos_jugados=500,
            monedas_ganadas=45,
            fecha_dispositivo=now,
            fecha_servidor=now,
        ),
    ]
    session.add_all(eventos)
    estudiante.monedas_totales = sum(evento.monedas_ganadas for evento in eventos)


async def _seed_codigo_vinculacion(session: AsyncSession, id_grupo: int) -> None:
    codigo = await session.get(CodigoVinculacion, "LUDUDE")
    if codigo:
        return

    codigo = CodigoVinculacion(
        codigo="LUDUDE",
        id_grupo=id_grupo,
        expira_el=datetime.now(timezone.utc) + timedelta(days=3650),
        esta_usado=False,
    )
    session.add(codigo)