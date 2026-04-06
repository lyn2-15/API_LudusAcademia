"""
app/db/models.py
Modelos ORM que replican exactamente el esquema SQL de los documentos.

Tablas:
  docentes            — supabase_uid + datos del docente
  grupos              — salones vinculados a un docente
  codigos_vinculacion — códigos LUDUXX temporales (expiran)
  estudiantes         — UUID seudonimizado + alias + grupo
  eventos_aprendizaje — historial de misiones (idempotencia por PK)
  inventario          — cromos desbloqueados (UNIQUE por alumno+cromo)
"""
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey,
    Integer, String, Text
)
from sqlalchemy.orm import relationship
from app.db.session import Base


def utcnow():
    return datetime.now(timezone.utc)


class Docente(Base):
    __tablename__ = "docentes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    supabase_uid = Column(String, unique=True, nullable=False, index=True)
    correo = Column(String, unique=True, nullable=False)
    nombre_completo = Column(String, nullable=True)
    fecha_registro = Column(DateTime, default=utcnow, nullable=False)

    grupos = relationship("Grupo", back_populates="docente")


class Grupo(Base):
    __tablename__ = "grupos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    id_docente = Column(Integer, ForeignKey("docentes.id"), nullable=False)
    nombre_grupo = Column(String, nullable=False)
    nombre_escuela = Column(String, default="Escuela 5 de Mayo de 1862")

    docente = relationship("Docente", back_populates="grupos")
    estudiantes = relationship("Estudiante", back_populates="grupo")
    codigos = relationship("CodigoVinculacion", back_populates="grupo")


class CodigoVinculacion(Base):
    """
    Código temporal de 6 caracteres (ej. LUDU42).
    Un docente lo genera, el alumno lo ingresa en la app.
    Una vez usado, esta_usado = True y no puede reutilizarse.
    """
    __tablename__ = "codigos_vinculacion"

    codigo = Column(String(6), primary_key=True)
    id_grupo = Column(Integer, ForeignKey("grupos.id"), nullable=False)
    expira_el = Column(DateTime, nullable=False)
    esta_usado = Column(Boolean, default=False, nullable=False)

    grupo = relationship("Grupo", back_populates="codigos")


class Estudiante(Base):
    """
    Seudonimizado: solo UUID + alias (ej. "Explorador 1").
    La app móvil genera el UUID en el primer inicio.
    Nunca llega nombre real, CURP, ni dato identificable.
    """
    __tablename__ = "estudiantes"

    uuid_estudiante = Column(String, primary_key=True)   # UUID generado en la app
    id_grupo = Column(Integer, ForeignKey("grupos.id"), nullable=False)
    alias_estudiante = Column(String, nullable=True)      # "Alumno A", "Explorador 3"
    monedas_totales = Column(Integer, default=0, nullable=False)
    fecha_vinculacion = Column(DateTime, default=utcnow, nullable=False)

    grupo = relationship("Grupo", back_populates="estudiantes")
    eventos = relationship("EventoAprendizaje", back_populates="estudiante")
    inventario = relationship("Inventario", back_populates="estudiante")


class EventoAprendizaje(Base):
    """
    Registro atómico de una misión jugada.
    id_evento es PRIMARY KEY (UUID generado en el móvil).
    Si llega duplicado, SQLite lo rechaza silenciosamente → idempotencia.
    """
    __tablename__ = "eventos_aprendizaje"

    id_evento = Column(String, primary_key=True)         # UUID del móvil — garantiza idempotencia
    uuid_estudiante = Column(String, ForeignKey("estudiantes.uuid_estudiante"), nullable=False)
    id_mision = Column(String, nullable=False)            # Referencia al PDA
    errores = Column(Integer, default=0)
    segundos_jugados = Column(Integer, default=0)
    monedas_ganadas = Column(Integer, default=0)
    fecha_dispositivo = Column(DateTime, nullable=False)  # Hora real del juego (offline)
    fecha_servidor = Column(DateTime, default=utcnow)     # Hora de recepción en la API

    estudiante = relationship("Estudiante", back_populates="eventos")


class Inventario(Base):
    """
    Cromos del Códice de Luminiá desbloqueados por el alumno.
    UNIQUE(uuid_estudiante, id_cromo) → el mismo cromo no se duplica.
    """
    __tablename__ = "inventario"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid_estudiante = Column(String, ForeignKey("estudiantes.uuid_estudiante"), nullable=False)
    id_cromo = Column(String, nullable=False)
    desbloqueado_el = Column(DateTime, default=utcnow)

    estudiante = relationship("Estudiante", back_populates="inventario")

    from sqlalchemy import UniqueConstraint
    __table_args__ = (
        UniqueConstraint("uuid_estudiante", "id_cromo", name="uq_estudiante_cromo"),
    )
