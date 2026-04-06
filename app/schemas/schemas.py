"""
app/schemas/schemas.py
Modelos Pydantic v2: reflejan exactamente los contratos de los documentos.
Nombres en español para alinearse con el esquema de BD y los cURLs de ejemplo.
"""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, field_validator
import re


# ── Vinculación de dispositivo ────────────────────────────────────────────────

class VincularRequest(BaseModel):
    uuid_estudiante: str = Field(..., description="UUID generado por la app en el primer inicio")
    codigo_vinculacion: str = Field(..., min_length=6, max_length=6)

    @field_validator("codigo_vinculacion")
    @classmethod
    def codigo_uppercase(cls, v: str) -> str:
        return v.upper().strip()


class VincularResponse(BaseModel):
    mensaje: str
    id_grupo: int


# ── Sincronización de progreso ────────────────────────────────────────────────

class EventoAprendizajeIn(BaseModel):
    id_evento: str = Field(..., description="UUID generado en el móvil — garantiza idempotencia")
    id_mision: str = Field(..., max_length=100)
    errores: int = Field(0, ge=0)
    segundos_jugados: int = Field(0, ge=0, le=86400)
    monedas_ganadas: int = Field(0, ge=0)
    fecha_dispositivo: datetime


class SincronizarRequest(BaseModel):
    uuid_estudiante: str
    eventos: list[EventoAprendizajeIn] = Field(..., min_length=1, max_length=100)


class SincronizarResponse(BaseModel):
    estado: Literal["exito"]
    eventos_procesados: int
    duplicados_ignorados: int


# ── Generación de código de vinculación (docente) ─────────────────────────────

class GenerarCodigoRequest(BaseModel):
    id_grupo: int
    horas_validez: int = Field(24, ge=1, le=168)  # máx 1 semana


class GenerarCodigoResponse(BaseModel):
    codigo_vinculacion: str
    expira_el: datetime


# ── Analítica de grupo (docente) ──────────────────────────────────────────────

class MetricaAlumno(BaseModel):
    alias_alumno: str
    misiones_completas: int
    promedio_errores: float
    monedas_totales: int
    ultima_actividad: datetime | None


class AnaliticaGrupoResponse(BaseModel):
    id_grupo: int
    nombre_grupo: str
    total_alumnos: int
    metricas: list[MetricaAlumno]
    generado_el: datetime


# ── Health ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    estado: Literal["ok", "degradado"]
    version: str
    entorno: str
