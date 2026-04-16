"""
app/api/v1/endpoints/docentes.py
Endpoints del docente — acceso público para pruebas e integración.

POST /docentes/codigos                      — genera código LUDUXX
GET  /docentes/analitica/grupo/{id_grupo}   — métricas del grupo
GET  /docentes/reportes/pdf/{uuid}          — reporte PDF del alumno
"""
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.schemas import (
    AnaliticaGrupoResponse,
    GenerarCodigoRequest,
    GenerarCodigoResponse,
)
from app.services.docente_service import DocenteService

router = APIRouter(prefix="/docentes", tags=["📊 Docentes"])
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
        "Endpoint público para pruebas."
    ),
    responses={
        201: {"description": "Código generado."},
    },
)
async def generar_codigo(
    payload: GenerarCodigoRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GenerarCodigoResponse:
    return await service.generar_codigo(db, payload)


@router.get(
    "/analitica/grupo/{id_grupo}",
    response_model=AnaliticaGrupoResponse,
    summary="Analítica del grupo",
    description=(
        "Devuelve métricas pedagógicas de todos los alumnos del grupo. "
        "Usa el parámetro `?metrica=errores` o `?metrica=progreso` para ordenar. "
        "Los alumnos aparecen con alias — nunca con nombre real. "
        "Endpoint público para pruebas."
    ),
    responses={
        200: {"description": "Métricas del grupo."},
    },
)
async def analitica_grupo(
    id_grupo: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    metrica: Literal["errores", "progreso"] | None = Query(
        None, description="Ordena los alumnos por esta métrica."
    ),
) -> AnaliticaGrupoResponse:
    return await service.analitica_grupo(db, id_grupo, metrica)


@router.get(
    "/reportes/pdf/{uuid_estudiante}",
    summary="Reporte PDF del alumno",
    description=(
        "Genera un PDF de progreso individual. "
        "El reporte usa el alias o UUID del alumno — nunca su nombre real. "
        "Endpoint público para pruebas."
    ),
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
async def reporte_pdf(
    uuid_estudiante: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from app.db.models import Estudiante, Grupo
    from fastapi import HTTPException

    # Cargar alumno y grupo sin validación de identidad para permitir pruebas desde la web.
    estudiante = await db.get(Estudiante, uuid_estudiante)
    if not estudiante:
        raise HTTPException(status_code=404, detail="Alumno no encontrado.")

    grupo = await db.get(Grupo, estudiante.id_grupo)
    if not grupo:
        raise HTTPException(status_code=404, detail="Grupo no encontrado.")

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
