"""
app/services/estudiante_service.py
Lógica de negocio para alumnos:
  - Vinculación por código LUDUXX
  - Sincronización de eventos con idempotencia nativa de SQLite
"""
import random
import string
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import CodigoVinculacion, Estudiante, EventoAprendizaje, Grupo
from app.schemas.schemas import (
    EventoAprendizajeIn,
    SincronizarRequest,
    SincronizarResponse,
    VincularRequest,
    VincularResponse,
)

settings = get_settings()


class EstudianteService:

    # ── Vinculación ───────────────────────────────────────────────────────────

    async def vincular(
        self, db: AsyncSession, payload: VincularRequest
    ) -> VincularResponse:
        """
        Vincula un UUID de dispositivo con un grupo escolar.

        Flujo:
          1. Busca el código → verifica que existe, no expiró y no fue usado.
          2. Crea (o actualiza) el registro del estudiante.
          3. Marca el código como usado.
        """
        ahora = datetime.now(timezone.utc)

        # 1. Validar código
        codigo = await db.get(CodigoVinculacion, payload.codigo_vinculacion)

        if not codigo:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Código de vinculación inválido o expirado.",
            )
        if codigo.esta_usado or codigo.expira_el.replace(tzinfo=timezone.utc) < ahora:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Código de vinculación inválido o expirado.",
            )

        # 2. Crear o actualizar estudiante (idempotente: si ya existe, no falla)
        estudiante = await db.get(Estudiante, payload.uuid_estudiante)
        if not estudiante:
            # Asignar alias automático basado en el número de alumnos del grupo
            total = await db.scalar(
                select(func.count(Estudiante.uuid_estudiante))
                .where(Estudiante.id_grupo == codigo.id_grupo)
            )
            alias = f"Alumno {(total or 0) + 1}"

            estudiante = Estudiante(
                uuid_estudiante=payload.uuid_estudiante,
                id_grupo=codigo.id_grupo,
                alias_estudiante=alias,
            )
            db.add(estudiante)

        # 3. Marcar código como usado (un código → un alumno)
        codigo.esta_usado = True

        return VincularResponse(
            mensaje="Dispositivo vinculado con éxito.",
            id_grupo=codigo.id_grupo,
        )

    # ── Sincronización ────────────────────────────────────────────────────────

    async def sincronizar(
        self, db: AsyncSession, payload: SincronizarRequest
    ) -> SincronizarResponse:
        """
        Recibe el volcado de eventos del modo offline.

        Idempotencia: id_evento es PRIMARY KEY en SQLite.
        Si un evento ya existe, la BD lanza IntegrityError → se cuenta
        como duplicado y se ignora. El alumno nunca pierde monedas
        por un reintento de conexión.

        Seguridad: verifica que el UUID del alumno esté vinculado a un grupo
        antes de aceptar cualquier dato.
        """
        # Verificar que el alumno está vinculado
        estudiante = await db.get(Estudiante, payload.uuid_estudiante)
        if not estudiante:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="El dispositivo no está vinculado a ningún grupo.",
            )

        procesados = 0
        duplicados = 0
        monedas_nuevas = 0

        for evento in payload.eventos:
            nuevo = EventoAprendizaje(
                id_evento=evento.id_evento,
                uuid_estudiante=payload.uuid_estudiante,
                id_mision=evento.id_mision,
                errores=evento.errores,
                segundos_jugados=evento.segundos_jugados,
                monedas_ganadas=evento.monedas_ganadas,
                fecha_dispositivo=evento.fecha_dispositivo,
            )
            db.add(nuevo)
            try:
                await db.flush()   # Detecta PK duplicada sin hacer commit completo
                procesados += 1
                monedas_nuevas += evento.monedas_ganadas
            except IntegrityError:
                await db.rollback()
                duplicados += 1

        # Actualizar monedas totales solo con eventos nuevos (atómico)
        if monedas_nuevas > 0:
            estudiante.monedas_totales += monedas_nuevas

        return SincronizarResponse(
            estado="exito",
            eventos_procesados=procesados,
            duplicados_ignorados=duplicados,
        )


# ── Generación de códigos ─────────────────────────────────────────────────────

def generar_codigo_ludu() -> str:
    """
    Genera un código alfanumérico de 6 caracteres con prefijo LUDU.
    Ejemplo: LUDU42, LUDU7X, LUDUAB
    Usa solo caracteres fáciles de leer (sin O/0, I/1 para evitar confusión).
    """
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    sufijo = "".join(random.choices(chars, k=2))
    return f"LUDU{sufijo}"
