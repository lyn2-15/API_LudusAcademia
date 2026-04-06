"""
tests/unit/test_v2_logica.py
Tests unitarios para los dos mecanismos críticos de la v2:
  1. Vinculación por código LUDUXX
  2. Idempotencia en la sincronización de eventos
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.schemas import (
    EventoAprendizajeIn,
    SincronizarRequest,
    VincularRequest,
)
from app.services.estudiante_service import EstudianteService, generar_codigo_ludu


# ── Generador de códigos ──────────────────────────────────────────────────────

def test_codigo_ludu_formato():
    """El código debe ser exactamente 6 chars y empezar con LUDU."""
    for _ in range(50):
        codigo = generar_codigo_ludu()
        assert len(codigo) == 6
        assert codigo.startswith("LUDU")
        # Sin caracteres confusos (O, 0, I, 1)
        sufijo = codigo[4:]
        assert "O" not in sufijo
        assert "0" not in sufijo
        assert "I" not in sufijo
        assert "1" not in sufijo


def test_codigos_no_son_todos_iguales():
    """El generador debe producir variedad suficiente."""
    codigos = {generar_codigo_ludu() for _ in range(30)}
    assert len(codigos) > 15  # Alta probabilidad de tener >15 únicos en 30


# ── Vinculación ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_vincular_codigo_expirado_lanza_404():
    """Un código expirado debe devolver 404, no vincular al alumno."""
    service = EstudianteService()
    payload = VincularRequest(uuid_estudiante="uuid-test-001", codigo_vinculacion="LUDU42")

    codigo_mock = MagicMock()
    codigo_mock.esta_usado = False
    # Expirado hace 1 hora
    codigo_mock.expira_el = datetime.now(timezone.utc) - timedelta(hours=1)

    db = AsyncMock()
    db.add = MagicMock()
    db.get.return_value = codigo_mock

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await service.vincular(db, payload)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_vincular_codigo_ya_usado_lanza_404():
    """Un código marcado como usado no debe permitir vinculación."""
    service = EstudianteService()
    payload = VincularRequest(uuid_estudiante="uuid-test-002", codigo_vinculacion="LUDU99")

    codigo_mock = MagicMock()
    codigo_mock.esta_usado = True  # ← Ya fue usado
    codigo_mock.expira_el = datetime.now(timezone.utc) + timedelta(hours=23)

    db = AsyncMock()
    db.get.return_value = codigo_mock

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await service.vincular(db, payload)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_vincular_dispositivo_no_existente_crea_perfil():
    """Un UUID nuevo debe crear el perfil del estudiante."""
    service = EstudianteService()
    payload = VincularRequest(uuid_estudiante="uuid-nuevo-123", codigo_vinculacion="LUDUAB")

    codigo_mock = MagicMock()
    codigo_mock.esta_usado = False
    codigo_mock.expira_el = datetime.now(timezone.utc) + timedelta(hours=24)
    codigo_mock.id_grupo = 5

    db = AsyncMock()
    # Primer get: código existe; segundo get: estudiante NO existe
    db.get.side_effect = [codigo_mock, None]
    db.scalar.return_value = 3  # 3 alumnos ya en el grupo → alias "Alumno 4"

    result = await service.vincular(db, payload)

    assert result.id_grupo == 5
    assert "éxito" in result.mensaje.lower()
    db.add.assert_called_once()  # Se creó el perfil


# ── Sincronización e idempotencia ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sync_alumno_no_vinculado_lanza_403():
    """Un UUID no registrado debe ser rechazado con 403."""
    service = EstudianteService()
    payload = SincronizarRequest(
        uuid_estudiante="uuid-desconocido",
        eventos=[
            EventoAprendizajeIn(
                id_evento="evt-001",
                id_mision="fraccion_01",
                errores=2,
                segundos_jugados=90,
                monedas_ganadas=50,
                fecha_dispositivo=datetime.now(timezone.utc),
            )
        ],
    )

    db = AsyncMock()
    db.get.return_value = None  # Alumno no existe

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await service.sincronizar(db, payload)

    assert exc_info.value.status_code == 403


def test_schema_evento_rechaza_tiempo_negativo():
    """El schema Pydantic debe rechazar segundos_jugados negativos."""
    with pytest.raises(Exception):
        EventoAprendizajeIn(
            id_evento="evt-002",
            id_mision="geo_01",
            errores=0,
            segundos_jugados=-5,  # ← inválido
            monedas_ganadas=100,
            fecha_dispositivo=datetime.now(timezone.utc),
        )


def test_schema_codigo_vinculacion_normaliza_a_mayusculas():
    """El código debe normalizarse a mayúsculas aunque llegue en minúsculas."""
    req = VincularRequest(uuid_estudiante="uuid-xyz", codigo_vinculacion="ludu42")
    assert req.codigo_vinculacion == "LUDU42"
