# LudusAcademia+ API — v2

Bridge offline-first entre la app Android y el Dashboard Docente.
**Stack:** FastAPI · SQLite3 (aiosqlite) · Supabase Auth

---

## Qué cambió respecto a la v1

| Aspecto | v1 | v2 |
|---|---|---|
| Base de datos | PostgreSQL + asyncpg | **SQLite3 + aiosqlite** |
| Auth docentes | JWT propio (8h) | **Supabase Auth (JWT externo)** |
| Registro de docentes | Endpoint manual | **Auto-provisioning en primer login** |
| Vinculación alumno | UUID directo en payload | **Código LUDUXX de 6 caracteres** |
| Endpoints móvil | `/sync/progress`, `/sync/inventory` | **`/estudiantes/vincular`, `/estudiantes/sincronizar`** |
| Endpoints docente | `/analytics/group/{id}` | **`/docentes/analitica/grupo/{id}`** |
| Despliegue | Docker + PostgreSQL service | **Docker solo (SQLite embebido)** |

---

## Levantamiento rápido

```bash
# 1. Copiar variables de entorno
cp .env.example .env

# 2. Completar SUPABASE_URL y SUPABASE_JWT_SECRET
#    (Supabase Dashboard → Project Settings → API → JWT Secret)
nano .env

# 3. Levantar
docker compose up --build

# Swagger UI disponible en:
#   http://localhost:8000/docs
```

---

## Endpoints

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| `GET` | `/v1/health` | — | Estado del servidor |
| `POST` | `/v1/estudiantes/vincular` | — | Une UUID al grupo via código LUDUXX |
| `POST` | `/v1/estudiantes/sincronizar` | — | Volcado de eventos offline |
| `POST` | `/v1/docentes/codigos` | JWT Supabase | Genera código LUDUXX |
| `GET` | `/v1/docentes/analitica/grupo/{id}` | JWT Supabase | Métricas del grupo |
| `GET` | `/v1/docentes/reportes/pdf/{uuid}` | JWT Supabase | Reporte PDF del alumno |

---

## Flujo de vinculación (nuevo en v2)

```
Docente (web)              API                    Alumno (app)
──────────────────────────────────────────────────────────────
POST /docentes/codigos  →  genera "LUDU42"
                           expira en 24h

                           ←────────────────── Alumno ingresa "LUDU42"
                           POST /estudiantes/vincular
                           valida código, crea perfil
                           marca código como usado
                           ──────────────────→ {"id_grupo": 5}

                           ←────────────────── WorkManager detecta red
                           POST /estudiantes/sincronizar
                           {"uuid_estudiante":"...", "eventos":[...]}
                           idempotencia: duplicados ignorados
                           ──────────────────→ {"eventos_procesados": 7}
```

---

## Idempotencia en sincronización

`id_evento` es la clave primaria de `eventos_aprendizaje`. Si el WorkManager
reintenta un envío por caída de red, SQLite rechaza el duplicado con un
`IntegrityError` que el servicio captura silenciosamente. El cliente recibe:

```json
{
  "estado": "exito",
  "eventos_procesados": 0,
  "duplicados_ignorados": 7
}
```

Este `200 OK` le indica al móvil que puede limpiar su cola de envío.

---

## Supabase Auth — cómo funciona

1. El docente hace login en el panel web con Supabase Auth (email/password).
2. Supabase devuelve un JWT firmado con `SUPABASE_JWT_SECRET`.
3. El dashboard envía ese JWT como `Authorization: Bearer <token>` a la API.
4. FastAPI valida la firma localmente — **sin llamadas HTTP a Supabase**.
5. El `sub` del JWT es el `supabase_uid`, que la API usa para identificar al docente.

Si el docente se autentica por primera vez, la API crea su perfil automáticamente
en la tabla `docentes` (auto-provisioning).

---

## Nota sobre SQLite en producción

SQLite serializa los writes (un writer a la vez). Para una escuela con
30-50 alumnos sincronizando en ventanas distintas, es perfectamente viable.

Se activa `PRAGMA journal_mode=WAL` al arrancar, que permite lecturas
concurrentes mientras hay un write en curso.

Si el proyecto escala a cientos de grupos simultáneos, el cambio a PostgreSQL
requiere solo modificar `DATABASE_URL` en `.env` — el resto del código es idéntico.

## Datos de prueba en producción

Si necesitas un despliegue con contenido inicial para probar el flujo sin crear
datos manualmente, activa `SEED_SAMPLE_DATA=true`. La API cargará un docente,
un grupo, un alumno, un código de vinculación y un evento de ejemplo, pero solo
si la base está vacía.

Valores por defecto del seed:
- Docente: `maestro@test.com`
- Grupo: `Grupo Demo`
- Código: `LUDUDE`

---

## Tests

```bash
pip install -r requirements.txt
pytest tests/ -v
# python -m pytest tests/ -v

# Esperado:
# test_codigo_ludu_formato               PASSED
# test_codigos_no_son_todos_iguales      PASSED
# test_vincular_codigo_expirado_...      PASSED
# test_vincular_codigo_ya_usado_...      PASSED
# test_vincular_dispositivo_no_...       PASSED
# test_sync_alumno_no_vinculado_...      PASSED
# test_schema_evento_rechaza_tiempo_...  PASSED
# test_schema_codigo_vinculacion_...     PASSED
```

---

## Estructura del proyecto

```
ludusacademia_v2/
├── app/
│   ├── main.py                        # FastAPI + lifespan + middlewares
│   ├── api/v1/
│   │   ├── router.py
│   │   └── endpoints/
│   │       ├── estudiantes.py         # vincular + sincronizar
│   │       ├── docentes.py            # codigos + analitica + pdf
│   │       └── health.py
│   ├── core/
│   │   ├── config.py                  # Settings desde .env
│   │   └── security.py               # Validación JWT Supabase
│   ├── db/
│   │   ├── session.py                 # Motor aiosqlite + WAL
│   │   └── models.py                  # 6 tablas SQLAlchemy ORM
│   ├── schemas/
│   │   └── schemas.py                 # Pydantic v2
│   └── services/
│       ├── estudiante_service.py      # Vinculación + sync + idempotencia
│       ├── docente_service.py         # Códigos LUDUXX + analítica + RLS
│       └── reporte_service.py         # PDF con ReportLab
├── tests/unit/
│   └── test_v2_logica.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```
