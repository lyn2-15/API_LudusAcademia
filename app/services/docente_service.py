"""
app/services/docente_service.py
Lógica de negocio para docentes:
  - Generación de códigos LUDUXX con expiración
  - Analítica del grupo con RLS: el docente solo ve sus grupos
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import CodigoVinculacion, Docente, Estudiante, EventoAprendizaje, Grupo
from app.schemas.schemas import (
    AnaliticaGrupoResponse,
    GenerarCodigoRequest,
    GenerarCodigoResponse,
    MetricaAlumno,
)
from app.services.estudiante_service import generar_codigo_ludu

settings = get_settings()


class DocenteService:

    async def obtener_o_crear_docente(
        self, db: AsyncSession, supabase_uid: str, correo: str = ""
    ) -> Docente:
        """
        Obtiene el registro del docente por su supabase_uid.
        Si es la primera vez que se autentica, crea su perfil automáticamente.
        Así no necesitamos un endpoint de registro separado.
        """
        result = await db.execute(
            select(Docente).where(Docente.supabase_uid == supabase_uid)
        )
        docente = result.scalar_one_or_none()

        if not docente:
            docente = Docente(
                supabase_uid=supabase_uid,
                correo=correo,
            )
            db.add(docente)
            await db.flush()

        return docente

    # ── Códigos de vinculación ────────────────────────────────────────────────

    async def generar_codigo(
        self, db: AsyncSession, supabase_uid: str, payload: GenerarCodigoRequest
    ) -> GenerarCodigoResponse:
        """
        Genera un código LUDUXX para que nuevos alumnos entren al grupo.

        RLS: verifica que el grupo pertenezca al docente autenticado.
        El código expira en `horas_validez` horas (default 24h).
        Reintenta si el código ya existe (colisión rara pero posible).
        """
        docente = await self.obtener_o_crear_docente(db, supabase_uid)

        # RLS: el grupo debe pertenecer a este docente
        grupo = await db.get(Grupo, payload.id_grupo)
        if not grupo or grupo.id_docente != docente.id:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para generar códigos en este grupo.",
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
        self, db: AsyncSession, supabase_uid: str, id_grupo: int, metrica: str | None
    ) -> AnaliticaGrupoResponse:
        """
        Devuelve métricas pedagógicas del grupo para el dashboard.
        Soporta filtro por ?metrica=errores o ?metrica=progreso.

        RLS: el docente solo puede consultar sus propios grupos.
        Los alumnos aparecen como alias, nunca con nombre real.
        """
        docente = await self.obtener_o_crear_docente(db, supabase_uid)

        grupo = await db.get(Grupo, id_grupo)
        if not grupo or grupo.id_docente != docente.id:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para consultar este grupo.",
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
