"""
app/core/security.py
Validación del JWT emitido por Supabase Auth.

Diferencia clave con v1: ya no generamos tokens propios.
FastAPI actúa como "Resource Server" — confía en el JWT de Supabase
verificando su firma con la clave correspondiente al algoritmo del token.

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


def _get_verification_key(alg: str) -> str:
    """Devuelve la clave correcta para validar el JWT según su algoritmo."""
    if alg == "HS256":
        return settings.SUPABASE_JWT_SECRET

    if alg == "ES256":
        if not settings.SUPABASE_JWT_PUBLIC_KEY:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    "Falta SUPABASE_JWT_PUBLIC_KEY para validar tokens ES256. "
                    "Configura la clave pública del proyecto en el entorno."
                ),
            )
        return settings.SUPABASE_JWT_PUBLIC_KEY

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=f"Algoritmo JWT no permitido: {alg}",
        headers={"WWW-Authenticate": "Bearer"},
    )


def verify_supabase_token(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict[str, Any]:
    """
    Dependencia FastAPI: extrae y valida el Bearer JWT de Supabase.
    Devuelve el payload completo (incluye 'sub' = supabase_uid del docente).

    Supabase puede firmar con HS256 o ES256.
    No hay llamada HTTP a Supabase — la validación es local y rápida.
    """
    token = credentials.credentials
    try:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg")
        if not alg or not isinstance(alg, str):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="JWT sin encabezado 'alg' válido.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        verification_key = _get_verification_key(alg)

        payload = jwt.decode(
            token,
            verification_key,
            algorithms=[alg],
            options={"verify_aud": False},  # Supabase no usa 'aud' por defecto
        )
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
