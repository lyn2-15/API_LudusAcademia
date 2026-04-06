"""
app/api/v1/endpoints/estudiantes.py
Endpoints del alumno (no requieren JWT — usan uuid_estudiante como identidad).

POST /estudiantes/vincular    — primera vez, une el dispositivo a un grupo
POST /estudiantes/sincronizar — volcado de eventos offline
"""
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.schemas import SincronizarRequest, SincronizarResponse, VincularRequest, VincularResponse
from app.services.estudiante_service import EstudianteService

router = APIRouter(prefix="/estudiantes", tags=["📱 Alumnos"])
settings = get_settings()
service = EstudianteService()

MAX_BYTES = settings.MAX_SYNC_PAYLOAD_KB * 1024


async def _check_size(request: Request):
    body = await request.body()
    if len(body) > MAX_BYTES:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=413,
            detail=f"Payload supera el límite de {settings.MAX_SYNC_PAYLOAD_KB}KB.",
        )


@router.post(
    "/vincular",
    response_model=VincularResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Vincular dispositivo al grupo",
    description=(
        "Une el UUID del dispositivo con un grupo escolar mediante el código LUDUXX "
        "que el docente generó. Operación pública — no requiere JWT. "
        "Si el código expiró o ya fue usado, devuelve 404."
    ),
    responses={
        201: {"description": "Dispositivo vinculado con éxito."},
        404: {"description": "Código de vinculación inválido o expirado."},
        422: {"description": "Formato del payload incorrecto."},
    },
)
async def vincular_dispositivo(
    payload: VincularRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> VincularResponse:
    return await service.vincular(db, payload)


@router.post(
    "/sincronizar",
    response_model=SincronizarResponse,
    status_code=status.HTTP_200_OK,
    summary="Sincronizar eventos de aprendizaje",
    description=(
        "Recibe el volcado de eventos acumulados en modo offline. "
        "**Idempotente**: eventos con `id_evento` duplicado se cuentan "
        "como `duplicados_ignorados` sin afectar el progreso del alumno. "
        "Rechaza el request si el `uuid_estudiante` no está vinculado a ningún grupo."
    ),
    responses={
        200: {"description": "Eventos procesados correctamente."},
        403: {"description": "El dispositivo no está vinculado a ningún grupo."},
        413: {"description": "Payload supera el límite de 50KB."},
    },
    dependencies=[Depends(_check_size)],
)
async def sincronizar_progreso(
    payload: SincronizarRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SincronizarResponse:
    return await service.sincronizar(db, payload)
