"""
app/services/docente_service.py
Lógica de negocio para docentes:
  - Generación de códigos LUDUXX con expiración
    - Analítica del grupo sin validación de identidad para pruebas
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CodigoVinculacion, Estudiante, EventoAprendizaje, Grupo
from app.schemas.schemas import (
    AnaliticaGrupoResponse,
    GenerarCodigoRequest,
    GenerarCodigoResponse,
    MetricaAlumno,
)
from app.services.estudiante_service import generar_codigo_ludu


class DocenteService:
    # ── Códigos de vinculación ────────────────────────────────────────────────

    async def generar_codigo(
        self, db: AsyncSession, payload: GenerarCodigoRequest
    ) -> GenerarCodigoResponse:
        """
        Genera un código LUDUXX para que nuevos alumnos entren al grupo.

        El código expira en `horas_validez` horas (default 24h).
        Reintenta si el código ya existe (colisión rara pero posible).
        """
        # Solo validar que el grupo exista para permitir pruebas sin auth.
        grupo = await db.get(Grupo, payload.id_grupo)
        if not grupo:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="El grupo no existe.",
            )

        expira = datetime.now(timezone.utc) + timedelta(hours=payload.horas_validez)

        # Generar código único (reintentar hasta encontrar uno libre)
        for _ in range(10):
            codigo_str = generar_codigo_ludu()
            existente = await db.get(CodigoVinculacion, codigo_str)
            if not existente:
                break

        nuevo_codigo = CodigoVinculacion(
            codigo=codigo_str,
            id_grupo=payload.id_grupo,
            expira_el=expira,
            esta_usado=False,
        )
        db.add(nuevo_codigo)

        return GenerarCodigoResponse(
            codigo_vinculacion=codigo_str,
            expira_el=expira,
        )

    # ── Analítica ─────────────────────────────────────────────────────────────

    async def analitica_grupo(
        self, db: AsyncSession, id_grupo: int, metrica: str | None
    ) -> AnaliticaGrupoResponse:
        """
        Devuelve métricas pedagógicas del grupo para el dashboard.
        Soporta filtro por ?metrica=errores o ?metrica=progreso.

        Los alumnos aparecen como alias, nunca con nombre real.
        """
        grupo = await db.get(Grupo, id_grupo)
        if not grupo:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="El grupo no existe.",
            )

        # Obtener alumnos del grupo
        result = await db.execute(
            select(Estudiante).where(Estudiante.id_grupo == id_grupo)
        )
        alumnos = result.scalars().all()

        metricas = []
        for alumno in alumnos:
            # Estadísticas de eventos
            stats = await db.execute(
                select(
                    func.count(EventoAprendizaje.id_evento).label("total_misiones"),
                    func.coalesce(func.avg(EventoAprendizaje.errores), 0.0).label("prom_errores"),
                    func.max(EventoAprendizaje.fecha_servidor).label("ultima_actividad"),
                ).where(EventoAprendizaje.uuid_estudiante == alumno.uuid_estudiante)
            )
            row = stats.one()

            metricas.append(MetricaAlumno(
                alias_alumno=alumno.alias_estudiante or alumno.uuid_estudiante[:8],
                misiones_completas=row.total_misiones or 0,
                promedio_errores=round(float(row.prom_errores), 2),
                monedas_totales=alumno.monedas_totales,
                ultima_actividad=row.ultima_actividad,
            ))

        # Ordenar por métrica solicitada
        if metrica == "errores":
            metricas.sort(key=lambda m: m.promedio_errores, reverse=True)
        elif metrica == "progreso":
            metricas.sort(key=lambda m: m.misiones_completas, reverse=True)

        return AnaliticaGrupoResponse(
            id_grupo=id_grupo,
            nombre_grupo=grupo.nombre_grupo,
            total_alumnos=len(metricas),
            metricas=metricas,
            generado_el=datetime.now(timezone.utc),
        )
