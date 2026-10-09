"""Dataclasses ligeras. La fuente de verdad es SQLite (database.py)."""
from dataclasses import dataclass

@dataclass
class Campana:
    id: int | None
    nombre: str
    descripcion: str = ""

@dataclass
class Personaje:
    id: int | None
    nombre: str
    clase: str = ""
    especie: str = ""
    nivel: int = 1
    campana_id: int | None = None
    localizacion_id: int | None = None
    battlemap_id: int | None = None
    token_x: float = 0
    token_y: float = 0
    color: str = "#e74c3c"
