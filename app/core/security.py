"""
app/core/security.py
Validación del JWT emitido por Supabase Auth.

Diferencia clave con v1: ya no generamos tokens propios.
FastAPI actúa como "Resource Server" — confía en el JWT de Supabase
verificando su firma con SUPABASE_JWT_SECRET (HMAC-SHA256).

El payload del JWT de Supabase incluye:
  - sub: UUID del docente en Supabase
  - email: correo del docente
  - exp: expiración
  - app_metadata / user_metadata: campos custom opcionales

RLS: después de validar el token, cada endpoint verifica que
el id_grupo consultado pertenezca al docente (via DB).
"""
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import get_settings

settings = get_settings()
bearer_scheme = HTTPBearer()
optional_bearer_scheme = HTTPBearer(auto_error=False)


def _decode_supabase_token(token: str) -> dict[str, Any]:
    return jwt.decode(
        token,
        settings.SUPABASE_JWT_SECRET,
        algorithms=["HS256"],
        options={"verify_aud": False},  # Supabase no usa 'aud' por defecto
    )


def verify_supabase_token(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict[str, Any]:
    """
    Dependencia FastAPI: extrae y valida el Bearer JWT de Supabase.
    Devuelve el payload completo (incluye 'sub' = supabase_uid del docente).

    Supabase firma con HS256 usando el JWT Secret del proyecto.
    No hay llamada HTTP a Supabase — la validación es local y rápida.
    """
    token = credentials.credentials
    try:
        payload = _decode_supabase_token(token)
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Sesión de Supabase inválida o expirada: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_supabase_uid(payload: dict = Depends(verify_supabase_token)) -> str:
    """Shortcut: extrae solo el supabase_uid (campo 'sub') del token."""
    uid = payload.get("sub")
    if not uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sin identificador de usuario (sub).",
        )
    return uid


def get_optional_supabase_uid(
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_bearer_scheme),
) -> str | None:
    """Devuelve el supabase_uid si hay token; en modo público permite acceso sin JWT."""
    if settings.ALLOW_PUBLIC_DOCENTE_ENDPOINTS:
        return None

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falta token Bearer de Supabase.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = _decode_supabase_token(credentials.credentials)
        uid = payload.get("sub")
        if not uid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token sin identificador de usuario (sub).",
            )
        return uid
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Sesión de Supabase inválida o expirada: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )
