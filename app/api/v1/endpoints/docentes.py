"""
app/api/v1/endpoints/docentes.py
Endpoints del docente — todos requieren JWT de Supabase.

POST /docentes/codigos                      — genera código LUDUXX
GET  /docentes/analitica/grupo/{id_grupo}   — métricas del grupo
GET  /docentes/reportes/pdf/{uuid}          — reporte PDF del alumno
"""
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import get_optional_supabase_uid, verify_supabase_token
from app.db.session import get_db
from app.schemas.schemas import (
    AnaliticaGrupoResponse,
    GenerarCodigoRequest,
    GenerarCodigoResponse,
)
from app.services.docente_service import DocenteService

settings = get_settings()

router = APIRouter(
    prefix="/docentes",
    tags=["📊 Docentes"],
    dependencies=[] if settings.ALLOW_PUBLIC_DOCENTE_ENDPOINTS else [Depends(verify_supabase_token)],
)
service = DocenteService()


@router.post(
    "/codigos",
    response_model=GenerarCodigoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generar código de vinculación",
    description=(
        "Genera un código alfanumérico de 6 caracteres (ej. `LUDU42`) "
        "para que nuevos alumnos se unan al grupo. "
        "El código expira según `horas_validez` (default: 24h). "
        "**RLS**: solo puedes generar códigos para tus propios grupos."
    ),
    responses={
        201: {"description": "Código generado."},
        401: {"description": "JWT inválido o expirado."},
        403: {"description": "El grupo no te pertenece."},
    },
)
async def generar_codigo(
    payload: GenerarCodigoRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    supabase_uid: Annotated[str | None, Depends(get_optional_supabase_uid)],
) -> GenerarCodigoResponse:
    return await service.generar_codigo(db, supabase_uid, payload)


@router.get(
    "/analitica/grupo/{id_grupo}",
    response_model=AnaliticaGrupoResponse,
    summary="Analítica del grupo",
    description=(
        "Devuelve métricas pedagógicas de todos los alumnos del grupo. "
        "Usa el parámetro `?metrica=errores` o `?metrica=progreso` para ordenar. "
        "Los alumnos aparecen con alias — nunca con nombre real. "
        "**RLS**: el JWT solo da acceso a tus grupos."
    ),
    responses={
        200: {"description": "Métricas del grupo."},
        403: {"description": "No tienes permisos para consultar este grupo."},
    },
)
async def analitica_grupo(
    id_grupo: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    supabase_uid: Annotated[str | None, Depends(get_optional_supabase_uid)],
    metrica: Literal["errores", "progreso"] | None = Query(
        None, description="Ordena los alumnos por esta métrica."
    ),
) -> AnaliticaGrupoResponse:
    return await service.analitica_grupo(db, supabase_uid, id_grupo, metrica)


@router.get(
    "/reportes/pdf/{uuid_estudiante}",
    summary="Reporte PDF del alumno",
    description=(
        "Genera un PDF de progreso individual. "
        "El reporte usa el alias o UUID del alumno — nunca su nombre real. "
        "**RLS**: el alumno debe pertenecer a uno de tus grupos."
    ),
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
async def reporte_pdf(
    uuid_estudiante: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    supabase_uid: Annotated[str | None, Depends(get_optional_supabase_uid)],
):
    from app.db.models import Estudiante, Grupo, Docente
    from app.services.docente_service import DocenteService
    from fastapi import HTTPException
    from sqlalchemy import select

    docente_svc = DocenteService()

    # Cargar alumno y verificar pertenencia al grupo del docente (RLS)
    estudiante = await db.get(Estudiante, uuid_estudiante)
    if not estudiante:
        raise HTTPException(status_code=404, detail="Alumno no encontrado.")

    grupo = await db.get(Grupo, estudiante.id_grupo)
    if not grupo:
        raise HTTPException(status_code=404, detail="Grupo no encontrado.")

    if not settings.ALLOW_PUBLIC_DOCENTE_ENDPOINTS:
        docente = await docente_svc.obtener_o_crear_docente(db, supabase_uid or "")
        if grupo.id_docente != docente.id:
            raise HTTPException(status_code=403, detail="No tienes acceso a este alumno.")

    # Generar PDF
    from app.services.reporte_service import ReporteService
    svc = ReporteService()
    pdf_bytes = await svc.generar_pdf(db, estudiante, grupo.nombre_grupo)

    alias = estudiante.alias_estudiante or uuid_estudiante[:8]
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=reporte_{alias}.pdf"},
    )
